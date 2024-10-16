from gpw_scraper.models import webhook as webhooks_models
from gpw_scraper.services.sqlalchemy import SQLAlchemyService


class SQLAWebhookUserService(SQLAlchemyService[webhooks_models.WebhookUser, int]):
    model = webhooks_models.WebhookUser


class SQLAWebhookEndpointService(
    SQLAlchemyService[webhooks_models.WebhookEndpoint, int]
):
    model = webhooks_models.WebhookEndpoint


class SQLAWebhookEventService(SQLAlchemyService[webhooks_models.WebhookEvent, int]):
    model = webhooks_models.WebhookEvent
