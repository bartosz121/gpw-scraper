import enum
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gpw_scraper.models.base import BaseModel
from gpw_scraper.models.mixins import TimestampMixin


class WebhookUser(BaseModel, TimestampMixin):
    __tablename__ = "webhook_users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True)
    api_key: Mapped[str] = mapped_column(String(128))


class WebhookEndpoint(BaseModel, TimestampMixin):
    __tablename__ = "webhook_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    url: Mapped[str] = mapped_column()
    secret: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("webhook_users.id"), index=True)


class WebhookEventType(enum.StrEnum):
    delivery_fail = "delivery_fail"
    delivery_fail_response = "delivery_fail_response"
    delivery_success = "delivery_success"


class WebhookEvent(BaseModel, TimestampMixin):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    type: Mapped[WebhookEventType] = mapped_column()
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhook_endpoints.id"), index=True)
    http_code: Mapped[int | None] = mapped_column(default=None)
    espi_ebi_id: Mapped[int] = mapped_column(ForeignKey("espi_ebi.id"), index=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
