from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from gpw_scraper.config import settings

metadata_ = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_N_label)s",
        "uq": "%(table_name)s_%(column_0_N_name)s_key",
        "ck": "%(table_name)s_%(constraint_name)s_check",
        "fk": "%(table_name)s_%(column_0_N_name)s_fkey",
        "pk": "%(table_name)s_pkey",
    }
)


engine = create_engine(settings.DB_URL, echo=settings.ENVIRONMENT.is_qa)

session_factory = sessionmaker(engine)


class BaseModel(AsyncAttrs, DeclarativeBase):  # noqa: PLW1641
    __abstract__ = True

    _eq_attr_name: str = "id"

    metadata = metadata_

    def __eq__(self, value: object) -> bool:
        self_eq_attr_val = getattr(self, self._eq_attr_name)
        value_eq_attr_val = getattr(value, self._eq_attr_name)

        if self_eq_attr_val is None or value_eq_attr_val is None:
            return False

        return isinstance(value, self.__class__) and self_eq_attr_val == value_eq_attr_val

    def __repr__(self) -> str:
        id_value = getattr(self, self._eq_attr_name)
        return f"{self.__class__.__name__}({self._eq_attr_name}={id_value!r})"
