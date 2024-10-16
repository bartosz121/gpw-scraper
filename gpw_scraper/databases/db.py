from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from gpw_scraper.config import settings

engine = create_async_engine(settings.DB_URL)

sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
