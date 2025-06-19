import os
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp
import httpx
import pytest
from aiohttp import web
from arq import create_pool
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gpw_scraper.api import create_app
from gpw_scraper.config import settings
from gpw_scraper.models.base import BaseModel

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "html")


@pytest.fixture
async def arq_pool():
    pool = await create_pool(settings.ARQ_REDIS_SETTINGS)
    return pool


@pytest.fixture
async def redis_conn():
    redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    await redis.flushall()
    yield redis
    await redis.aclose()


@pytest.fixture(scope="function")
async def db_sessionmaker() -> AsyncGenerator[async_sessionmaker[AsyncSession], Any]:
    engine = create_async_engine(settings.DB_URL)

    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
        await conn.run_sync(BaseModel.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    yield sessionmaker

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_sessionmaker):
    session: AsyncSession = db_sessionmaker()
    yield session
    await session.aclose()


@pytest.fixture
async def pap_test_client(aiohttp_client):
    async def pap_1(request: web.Request) -> web.Response:
        page_n = request.query["page"]
        path = os.path.join(HTML_PATH, f"page_{page_n}.html")
        if not os.path.exists(path):
            raise web.HTTPNotFound()

        with open(path, encoding="utf-8") as file:
            return web.Response(body=file.read())

    async def pap_2(request: web.Request) -> web.Response:
        r_id = request.match_info.get("id")
        if r_id is None:
            raise web.HTTPNotFound()

        path = os.path.join(HTML_PATH, f"{r_id}.html")
        if not os.path.exists(path):
            raise web.HTTPNotFound()

        with open(path, encoding="utf-8") as file:
            return web.Response(body=file.read())

    app = web.Application()
    app.router.add_get("/wyszukiwarka", pap_1)
    app.router.add_get("/node/{id}", pap_2)

    client = await aiohttp_client(app)
    client._base_url = ""
    yield client


@pytest.fixture
async def llm_rest_api_client(aiohttp_client):
    async def chat_completions(request: web.Request) -> web.Response:
        body = await request.json()
        req_model: str = body["model"]
        if req_model.startswith("respond_with"):
            fake_code = req_model.split("_")[-1]  # noqa: PLC0207

            class FakeError(web.HTTPException):
                status_code = int(fake_code)

            raise FakeError()

        return web.json_response(
            {
                "id": "id-1726251905923",
                "object": "chat.completion",
                "created": 1726251905,
                "model": req_model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"title":"LLM_TITLE","description":"LLM_DESCRIPTION"}',
                        },
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
            }
        )

    app = web.Application()
    app.router.add_post("/api/v1/chat/completions", chat_completions)

    client = await aiohttp_client(app)
    client._base_url = ""
    yield client


@pytest.fixture
async def open_router_client():
    async with aiohttp.ClientSession(
        base_url=settings.OPENROUTER_BASE_URL,
        headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
    ) as session:
        yield session


@pytest.fixture
async def api_client():
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
