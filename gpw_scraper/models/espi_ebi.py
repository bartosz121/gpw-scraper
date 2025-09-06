import enum
from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, Computed, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from gpw_scraper import utils
from gpw_scraper.models.base import BaseModel


class EntryType(enum.StrEnum):
    ESPI = "espi"
    EBI = "ebi"


class EspiEbi(BaseModel):
    __tablename__ = "espi_ebi"
    __table_args__ = (
        Index(
            "ix_espi_ebi_tsvector",
            "_tsvector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[EntryType] = mapped_column()
    title: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column()
    company: Mapped[str] = mapped_column()
    source: Mapped[str] = mapped_column(unique=True)
    parsed_by_llm: Mapped[str | None] = mapped_column()
    date: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utils.utc_now)

    _tsvector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            """
setweight(to_tsvector('pl_ispell', title), 'A') ||
setweight(to_tsvector('pl_ispell', description), 'B') ||
setweight(to_tsvector('pl_ispell', company), 'D')
""",
            persisted=True,
        ),
        deferred=True,
        deferred_raiseload=True,
    )
