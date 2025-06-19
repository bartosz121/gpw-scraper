from typing import Generic, TypeVar

from pydantic import BaseModel as BaseModel_
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class BaseSchema(BaseModel_):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)


class BaseSchemalId(BaseSchema, Generic[T]):
    id: T
