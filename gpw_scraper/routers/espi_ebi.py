from typing import Annotated

from fastapi import Depends, Query
from fastapi.routing import APIRouter
from sqlalchemy import select

from gpw_scraper import dependencies as deps
from gpw_scraper.models.espi_ebi import EntryType, EspiEbi
from gpw_scraper.schemas.espi_ebi import EspiEbiItem
from gpw_scraper.schemas.pagination import PaginatedResponse, PaginationParams
from gpw_scraper.services.sqlalchemy import OrderByBase

router = APIRouter()


@router.get("/espi-espi", response_model=PaginatedResponse[EspiEbiItem])
async def get_espi_ebi(
    espi_ebi_service: deps.EspiEbiService,
    pagination: Annotated[PaginationParams, Depends()],
    espi_or_ebi: Annotated[EntryType | None, Query(alias="filter")] = None,
):
    stmt = select(EspiEbi)
    if espi_or_ebi:
        stmt = stmt.where(EspiEbi.type == espi_or_ebi)

    items, total = await espi_ebi_service.list_and_count(
        statement=stmt,
        limit=pagination.limit,
        offset=pagination.offset,
        order_by=OrderByBase(field="date", order="desc"),
    )

    return {
        "items": items,
        "items_count": len(items),
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }
