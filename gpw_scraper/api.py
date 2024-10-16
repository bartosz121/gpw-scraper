from contextlib import asynccontextmanager
from typing import AsyncIterator, TypedDict

from fastapi import FastAPI

from gpw_scraper.routers.espi_ebi import router as espi_ebi_router
from gpw_scraper.routers.webhook import router as webhook_router


class State(TypedDict): ...


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    yield {}


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/")
    async def index():
        return {"msg": "ok"}

    app.include_router(espi_ebi_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/api/v1")

    return app
