from datetime import datetime

from pydantic import Field

from gpw_scraper.models.espi_ebi import EntryType
from gpw_scraper.schemas.base import BaseSchema


class EspiLLMSummary(BaseSchema):
    title: str = Field(
        max_length=128,
        description="Title of the ESPI must be short and concise, with no information about the company",
    )
    description: str = Field(
        max_length=1024,
        description="Description of ESPI, without company information like address, NIP, REGON",
    )


class EspiEbiItem(BaseSchema):
    id: int
    type: EntryType
    title: str
    description: str | None
    company: str
    source: str
    parsed_by_llm: str | None
    date: datetime
