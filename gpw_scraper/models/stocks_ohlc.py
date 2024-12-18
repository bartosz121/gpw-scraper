import enum
from datetime import datetime

from sqlalchemy import TIMESTAMP, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from gpw_scraper import utils
from gpw_scraper.models.base import BaseModel


class OHLCDataSource(str, enum.Enum):
    YAHOO_FINANCE = "YAHOO_FINANCE"


class StockOHLC(BaseModel):
    __tablename__ = "stocks_ohlc"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(index=True)
    open: Mapped[Numeric] = mapped_column(Numeric(10, 4))
    high: Mapped[Numeric] = mapped_column(Numeric(10, 4))
    low: Mapped[Numeric] = mapped_column(Numeric(10, 4))
    close: Mapped[Numeric] = mapped_column(Numeric(10, 4))
    date: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), index=True)
    source: Mapped[OHLCDataSource] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utils.utc_now
    )
