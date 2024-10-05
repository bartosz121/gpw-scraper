import enum
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from gpw_scraper.models.base import BaseModel


class EntryType(enum.Enum):
    ESPI = "espi"
    EBI = "ebi"


class EspiEbi(BaseModel):
    __tablename__ = "espi_ebi"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[EntryType] = mapped_column()
    title: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column()
    company: Mapped[str] = mapped_column()
    source: Mapped[str] = mapped_column(unique=True)
    parsed_by_llm: Mapped[str | None] = mapped_column()
    date: Mapped[datetime] = mapped_column()
