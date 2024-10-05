from typing import Annotated

from fastapi import Depends
from gpw_scraper.databases.db import sessionmaker as db_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession


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
