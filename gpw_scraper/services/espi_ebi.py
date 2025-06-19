from datetime import datetime

from sqlalchemy import func as sqla_func
from sqlalchemy import select

from gpw_scraper.models.espi_ebi import EspiEbi
from gpw_scraper.services.sqlalchemy import SQLAlchemyService


class SQLAEspiEbiService(SQLAlchemyService[EspiEbi, int]):
    model = EspiEbi

    async def list_in_date_range(self, date_start: datetime, date_end: datetime) -> list[EspiEbi]:
        stmt = select(EspiEbi).where(sqla_func.date(EspiEbi.date).between(date_start.date(), date_end.date()))
        return await self.list_(statement=stmt)
