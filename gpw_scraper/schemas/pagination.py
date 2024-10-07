from typing import Generic, TypeVar

from pydantic import Field

from gpw_scraper.schemas.base import BaseSchema

ModelT = TypeVar("ModelT")


class PaginationParams(BaseSchema):
    limit: int = Field(default=25, gt=0, le=100)
    offset: int = Field(0, ge=0)


class PaginatedResponse(BaseSchema, Generic[ModelT]):
    items: list[ModelT]
    items_count: int
    total: int
    limit: int
    offset: int
