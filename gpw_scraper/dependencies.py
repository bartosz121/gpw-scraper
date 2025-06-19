from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from gpw_scraper.databases.db import sessionmaker as db_sessionmaker
from gpw_scraper.services.espi_ebi import SQLAEspiEbiService
from gpw_scraper.services.webhook import (
    SQLAWebhookEndpointService,
    SQLAWebhookUserService,
)


async def get_db_session():
    async with db_sessionmaker() as session:
        try:
            yield session
        except:
            await session.rollback()
            raise
        else:
            await session.commit()


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_espi_ebi_service(db: DbSession) -> SQLAEspiEbiService:  # noqa: RUF029
    return SQLAEspiEbiService(db)


EspiEbiService = Annotated[SQLAEspiEbiService, Depends(get_espi_ebi_service)]


async def get_webhook_user_service(db: DbSession) -> SQLAWebhookUserService:  # noqa: RUF029
    return SQLAWebhookUserService(db)


WebhookUserService = Annotated[SQLAWebhookUserService, Depends(get_webhook_user_service)]


async def get_webhook_endpoint_service(db: DbSession) -> SQLAWebhookEndpointService:  # noqa: RUF029
    return SQLAWebhookEndpointService(db)


WebhookEndpointService = Annotated[SQLAWebhookEndpointService, Depends(get_webhook_endpoint_service)]
