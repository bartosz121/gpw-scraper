from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from gpw_scraper.models import mixins
from gpw_scraper.models.base import BaseModel


class TickerMetadata(BaseModel, mixins.TimestampMixin):
    __tablename__ = "tickers_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(index=True, unique=True)
    currency_symbol: Mapped[str] = mapped_column(index=True)
    full_name: Mapped[str] = mapped_column()
    sector: Mapped[str] = mapped_column(index=True)
    industry: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column(Text())
