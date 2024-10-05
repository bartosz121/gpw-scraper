from contextlib import asynccontextmanager
from typing import AsyncIterator, TypedDict

from fastapi import FastAPI


class State(TypedDict): ...


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    yield {}


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/")
    async def index():
        return {"msg": "ok"}

    return app
