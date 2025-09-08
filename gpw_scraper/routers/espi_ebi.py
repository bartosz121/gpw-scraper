from datetime import datetime
from typing import Annotated

from fastapi import Depends, Query
from fastapi.routing import APIRouter
from sqlalchemy import func, literal_column, select, text

from gpw_scraper import dependencies as deps
from gpw_scraper.models.espi_ebi import EntryType, EspiEbi
from gpw_scraper.schemas.espi_ebi import EspiEbiItem
from gpw_scraper.schemas.pagination import PaginatedResponse, PaginationParams
from gpw_scraper.services.sqlalchemy import OrderByBase

RANK_WEIGHTS = literal_column("ARRAY[0.1, 0.2, 0.8, 1.0]")

router = APIRouter()


@router.get("/espi-ebi", response_model=PaginatedResponse[EspiEbiItem])
async def get_espi_ebi(
    espi_ebi_service: deps.EspiEbiService,
    pagination: Annotated[
        PaginationParams,
        Depends(),
    ],
    espi_or_ebi: Annotated[
        EntryType | None,
        Query(alias="filter"),
    ] = None,
    company: Annotated[
        str | None,
        Query(
            description="Filter by company; uses `ILIKE q`\n\n`%` allowed, e.g. `%orlen%`",
        ),
    ] = None,
    date_start: Annotated[
        datetime | None,
        Query(
            alias="date-start",
            description="ISO 8601",
            example="2025-09-01T08:19:21+00:00",
        ),
    ] = None,
    date_end: Annotated[
        datetime | None,
        Query(
            alias="date-end",
            description="ISO 8601",
            example="2025-09-01T15:42:55+00:00",
        ),
    ] = None,
    fts: Annotated[
        str | None,
        Query(description="FTS"),
    ] = None,
):
    stmt = select(EspiEbi)

    if espi_or_ebi:
        stmt = stmt.where(EspiEbi.type == espi_or_ebi)

    if date_start:
        stmt = stmt.where(EspiEbi.date >= date_start)

    if date_end:
        stmt = stmt.where(EspiEbi.date <= date_end)

    if company:
        stmt = stmt.where(EspiEbi.company.ilike(company))

    if fts:
        ts_fts = func.plainto_tsquery("pl_ispell", fts)

        stmt = (
            stmt.add_columns(func.ts_rank(RANK_WEIGHTS, EspiEbi._tsvector, ts_fts).label("rank"))
            .where(EspiEbi._tsvector.op("@@")(ts_fts))
            .order_by(text("rank desc"))
        )

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
