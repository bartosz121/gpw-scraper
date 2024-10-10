from datetime import datetime

from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from gpw_scraper import utils


class TimestampMixin:
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=utils.utc_now,
        index=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        onupdate=utils.utc_now,
        default=None,
        index=True,
    )
