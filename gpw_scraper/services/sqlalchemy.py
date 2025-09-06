from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any, Generic, Literal, NamedTuple, TypeVar

from loguru import logger
from sqlalchemy import Column, Select, asc, desc, over, select, text
from sqlalchemy import func as sqla_func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyServiceError(Exception): ...


class ConflictError(SQLAlchemyServiceError): ...


class NotFoundError(SQLAlchemyServiceError): ...


class OrderByBase(NamedTuple):
    field: str
    order: Literal["asc", "desc"]


@contextmanager
def sql_error_handler():
    try:
        yield
    except IntegrityError as exc:
        logger.error(str(exc))
        raise ConflictError from exc
    except SQLAlchemyError as exc:
        logger.error(str(exc))
        msg = "An exception occured while executing SQL statement"
        raise SQLAlchemyServiceError(msg) from exc
    except AttributeError as exc:
        logger.error(str(exc))
        raise SQLAlchemyServiceError from exc


T = TypeVar("T")
U = TypeVar("U")
SelectT = TypeVar("SelectT", bound=Select[Any])

# List of kwargs which we don;t want to touch when "_where_from_kwargs" runs
RESERVED_KWARGS = {"offset", "limit", "order_by"}


class SQLAlchemyService(Generic[T, U]):
    model: type[T]
    model_id_attr_name: str = "id"
    model_id_type: type[U]

    def __init__(
        self,
        session: AsyncSession,
        *,
        statement: Select[tuple[T]] | None = None,
        auto_expunge: bool = False,
        auto_refresh: bool = True,
        auto_commit: bool = False,
    ) -> None:
        self.session = session
        self.statement = statement if statement is not None else select(self.model)
        self.auto_expunge = auto_expunge
        self.auto_refresh = auto_refresh
        self.auto_commit = auto_commit

    def _get_statement(self, statement: Select[tuple[T]] | None = None) -> Select[tuple[T]]:
        return self.statement if statement is None else statement

    def _get_model_id_attr(self) -> Column[U]:
        return getattr(self.model, self.model_id_attr_name)

    async def _attach_to_session(self, model: T, strategy: Literal["add", "merge"] = "add") -> T:
        if strategy == "add":
            self.session.add(model)
            return model
        if strategy == "merge":
            return await self.session.merge(model)

        msg = f"Strategy must be 'add' or 'merge', found:{strategy!r}"
        raise SQLAlchemyServiceError(msg)

    async def _flush_or_commit(self, *, auto_commit: bool | None) -> None:
        auto_commit = self.auto_commit if auto_commit is None else auto_commit

        return await self.session.commit() if auto_commit else await self.session.flush()

    async def _refresh(
        self,
        instance: T,
        attribute_names: Iterable[str] | None = None,
        *,
        auto_refresh: bool | None,
        with_for_update: bool | None = None,
    ) -> None:
        auto_refresh = self.auto_refresh if auto_refresh is None else auto_refresh

        return (
            await self.session.refresh(
                instance,
                attribute_names=attribute_names,
                with_for_update=with_for_update,
            )
            if auto_refresh
            else None
        )

    def _expunge(self, instance: T, *, auto_expunge: bool | None = None) -> None:
        auto_expunge = self.auto_expunge if auto_expunge is None else auto_expunge

        return self.session.expunge(instance) if auto_expunge else None

    def _where_from_kwargs(self, statement: Select[tuple[T]], **kwargs: Any) -> Select[tuple[T]]:
        for k, v in kwargs.items():
            if k not in RESERVED_KWARGS:
                statement = statement.where(getattr(self.model, k) == v)
        return statement

    def _offset_from_kwargs(self, statement: Select[tuple[T]], **kwargs: Any) -> Select[tuple[T]]:  # noqa: PLR6301
        if offset := kwargs.get("offset"):
            statement = statement.offset(offset)
        return statement

    def _limit_from_kwargs(self, statement: Select[tuple[T]], **kwargs: Any) -> Select[tuple[T]]:  # noqa: PLR6301
        if limit := kwargs.get("limit"):
            statement = statement.limit(limit)
        return statement

    def _paginate_from_kwargs(self, statement: Select[tuple[T]], **kwargs: Any) -> Select[tuple[T]]:
        statement = self._offset_from_kwargs(statement, **kwargs)
        statement = self._limit_from_kwargs(statement, **kwargs)
        return statement

    def _order_by_from_kwargs(self, statement: Select[tuple[T]], **kwargs: Any) -> Select[tuple[T]]:
        if order_by := kwargs.get("order_by"):
            if not isinstance(order_by, OrderByBase):
                msg = "order_by argument is not of expected type"
                raise SQLAlchemyServiceError(msg)

            if order_by.order == "asc":
                statement = statement.order_by(
                    asc(getattr(self.model, order_by.field)),
                )
            else:
                statement = statement.order_by(desc(getattr(self.model, order_by.field)))

        return statement

    def check_not_found(self, item: T | None) -> T:  # noqa: PLR6301
        if item is None:
            msg = "No record found"
            raise NotFoundError(msg)
        return item

    async def count(self, statement: Select[tuple[T]] | None = None, **kwargs: Any) -> int:
        with sql_error_handler():
            statement = self._get_statement(statement)
            statement = self._where_from_kwargs(statement, **kwargs)
            statement_count = statement.with_only_columns(
                sqla_func.count(text("1")),
                maintain_column_froms=True,
            )

            result = await self.session.execute(statement_count)
            return result.scalar_one()

    async def create(
        self,
        data: T,
        *,
        auto_commit: bool | None = None,
        auto_refresh: bool | None = None,
        auto_expunge: bool | None = None,
    ) -> T:
        with sql_error_handler():
            instance = await self._attach_to_session(data)
            await self._flush_or_commit(auto_commit=auto_commit)
            await self._refresh(instance, auto_refresh=auto_refresh)
            self._expunge(instance, auto_expunge=auto_expunge)
            return instance

    async def delete(
        self,
        id_: U,
        *,
        auto_commit: bool | None = None,
        auto_expunge: bool | None = None,
    ) -> T:
        with sql_error_handler():
            instance = await self.get(id=id_)
            await self.session.delete(instance)
            await self._flush_or_commit(auto_commit=auto_commit)
            self._expunge(instance, auto_expunge=auto_expunge)
            return instance

    async def exists(self, **kwargs: Any) -> bool:
        exists = await self.count(**kwargs)
        return exists > 0

    async def get(
        self,
        *,
        statement: Select[tuple[T]] | None = None,
        auto_expunge: bool | None = None,
        **kwargs: Any,
    ) -> T:
        with sql_error_handler():
            statement = self._get_statement(statement)
            statement = self._where_from_kwargs(statement, **kwargs)

            instance = (await self.session.execute(statement)).scalar_one_or_none()
            instance = self.check_not_found(instance)
            self._expunge(instance, auto_expunge=auto_expunge)

            return instance

    async def get_one(
        self,
        *,
        statement: Select[tuple[T]] | None = None,
        auto_expunge: bool | None = None,
        **kwargs: Any,
    ) -> T:
        with sql_error_handler():
            statement = self._get_statement(statement)
            statement = self._where_from_kwargs(statement, **kwargs)

            instance = (await self.session.execute(statement)).scalar_one_or_none()
            instance = self.check_not_found(instance)
            self._expunge(instance, auto_expunge=auto_expunge)
            return instance

    async def get_one_or_none(
        self,
        statement: Select[tuple[T]] | None = None,
        *,
        auto_expunge: bool | None = None,
        **kwargs: Any,
    ) -> T | None:
        with sql_error_handler():
            statement = self._get_statement(statement)
            statement = self._where_from_kwargs(statement, **kwargs)

            instance = (await self.session.execute(statement)).scalar_one_or_none()
            if instance:
                self._expunge(instance, auto_expunge=auto_expunge)
            return instance

    async def list_(
        self,
        statement: Select[tuple[T]] | None = None,
        *,
        auto_expunge: bool | None = None,
        **kwargs: Any,
    ) -> list[T]:
        with sql_error_handler():
            statement = self._get_statement(statement)
            statement = self._where_from_kwargs(statement, **kwargs)
            statement = self._paginate_from_kwargs(statement, **kwargs)
            statement = self._order_by_from_kwargs(statement, **kwargs)

            items = list((await self.session.execute(statement)).scalars())
            for item in items:
                self._expunge(item, auto_expunge=auto_expunge)

            return items

    async def list_and_count(
        self,
        statement: Select[Any] | None = None,
        *,
        auto_expunge: bool | None = None,
        **kwargs: Any,
    ) -> tuple[list[T], int]:
        with sql_error_handler():
            stmt = self._get_statement(statement)
            stmt = self._where_from_kwargs(stmt, **kwargs)
            stmt = self._order_by_from_kwargs(stmt, **kwargs)
            stmt = self._paginate_from_kwargs(stmt, **kwargs)

            stmt = stmt.add_columns(over(sqla_func.count()))

            result = await self.session.execute(stmt)
            rows = result.all()

            total_count = 0
            items: list[T] = []

            for i, row in enumerate(rows):
                instance = row[0]
                count_value = row[-1]
                self._expunge(instance, auto_expunge=auto_expunge)
                items.append(instance)
                if i == 0:
                    total_count = count_value

            return items, total_count

    async def update(
        self,
        data: T,
        *,
        auto_commit: bool | None = None,
        auto_refresh: bool | None = None,
        auto_expunge: bool | None = None,
        attribute_names: Iterable[str] | None = None,
        with_for_update: bool | None = None,
    ) -> T:
        with sql_error_handler():
            data_id = getattr(data, self.model_id_attr_name)
            await self.get(id=data_id)
            instance = await self._attach_to_session(data, strategy="merge")
            await self._flush_or_commit(auto_commit=auto_commit)
            await self._refresh(
                instance,
                attribute_names=attribute_names,
                with_for_update=with_for_update,
                auto_refresh=auto_refresh,
            )
            self._expunge(instance, auto_expunge=auto_expunge)
            return instance
