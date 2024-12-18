from datetime import datetime

from sqlalchemy import TIMESTAMP, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from gpw_scraper import utils
from gpw_scraper.models.base import BaseModel


class CurrencyExchange(BaseModel):
    __tablename__ = "currency_exchange"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    currency: Mapped[str] = mapped_column(String(length=3))
    exchange_rate: Mapped[Numeric] = mapped_column(Numeric(10, 6))  # to PLN
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=utils.utc_now, index=True
    )
