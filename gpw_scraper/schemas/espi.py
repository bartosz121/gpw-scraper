from gpw_scraper.schemas.base import BaseSchema
from pydantic import Field


class EspiLLMSummary(BaseSchema):
    title: str = Field(
        max_length=128,
        description="Title of the ESPI must be short and concise, with no information about the company",
    )
    description: str = Field(
        max_length=1024,
        description="Description of ESPI, without company information like address, NIP, REGON",
    )
