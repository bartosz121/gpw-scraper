from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from gpw_scraper.databases.db import sessionmaker as db_sessionmaker
from gpw_scraper.services.espi_ebi import SQLAEspiEbiService


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


def get_espi_ebi_service(db: DbSession) -> SQLAEspiEbiService:
    return SQLAEspiEbiService(db)


EspiEbiService = Annotated[SQLAEspiEbiService, Depends(get_espi_ebi_service)]
