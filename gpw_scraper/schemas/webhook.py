from pydantic import HttpUrl

from gpw_scraper.schemas.base import BaseSchema


class WebookEndpointCreateSchema(BaseSchema):
    url: HttpUrl


class WebhhookEndpointCreateResponse(BaseSchema):
    id: int
    url: HttpUrl
    secret: str
