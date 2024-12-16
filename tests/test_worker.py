import base64
from datetime import datetime
from typing import TypedDict
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import web
from arq.connections import ArqRedis
from arq.worker import Worker
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gpw_scraper.config import settings
from gpw_scraper.llm import LLMClientManaged, ModelManager
from gpw_scraper.models import espi_ebi as espi_ebi_models
from gpw_scraper.models import webhook as webhook_models
from gpw_scraper.worker import (
    dispatch_send_webhook_tasks,
    scrape_pap_espi_ebi,
    send_webhook,
)


async def test_worker_job_scrape_pap_espi_ebi(
    arq_pool: ArqRedis,
    redis_conn: Redis,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    pap_test_client,
    llm_rest_api_client,
):
    openrouter_session = LLMClientManaged(
        settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        chat_completion_path="/api/v1/chat/completions",
        manager=ModelManager(
            models=["respond_with_429", "respond_with_500", "model_1", "model_2"],
            model_index_reset_delta=settings.MODEL_MANAGER_INDEX_RESET_DELTA,
        ),
    )
    await openrouter_session._client.close()
    openrouter_session._client = llm_rest_api_client

    cloudflare_ai_session = LLMClientManaged(
        settings.CLOUDFLARE_AI_BASE_URL,
        api_key=settings.CLOUDFLARE_AI_API_KEY,
        chat_completion_path="/api/v1/chat/completions",
        manager=ModelManager(
            models=["respond_with_429", "respond_with_500", "model_1", "model_2"],
            model_index_reset_delta=settings.MODEL_MANAGER_INDEX_RESET_DELTA,
        ),
    )
    await cloudflare_ai_session._client.close()
    cloudflare_ai_session._client = llm_rest_api_client

    openai_session = LLMClientManaged(
        settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        chat_completion_path="/api/v1/chat/completions",
        manager=ModelManager(
            models=["respond_with_429", "respond_with_500", "model_1", "model_2"],
            model_index_reset_delta=settings.MODEL_MANAGER_INDEX_RESET_DELTA,
        ),
    )
    await openai_session._client.close()
    openai_session._client = llm_rest_api_client

    async def startup(ctx):
        ctx["redis_client"] = redis_conn
        ctx["pap_session"] = pap_test_client
        ctx["openrouter_session"] = openrouter_session
        ctx["cloudflare_ai_session"] = cloudflare_ai_session
        ctx["openai_session"] = openai_session
        ctx["db_sessionmaker"] = db_sessionmaker

    async def shutdown(ctx):
        await ctx["redis_client"].aclose()
        await ctx["pap_session"].close()
        await ctx["pap_session"].close()
        await ctx["openrouter_session"].close()
        await ctx["cloudflare_ai_session"].close()
        await ctx["openai_session"].close()
        await ctx["db_sessionmaker"].close()

    worker = Worker(
        on_startup=startup,
        on_shutdown=shutdown,
        functions=[scrape_pap_espi_ebi],
        burst=True,
        poll_delay=0,
        queue_read_limit=10,
        redis_settings=settings.ARQ_REDIS_SETTINGS,
    )

    dt = datetime(year=2024, month=7, day=22)
    await arq_pool.enqueue_job("scrape_pap_espi_ebi", dt, dt)

    await worker.main()

    # Everything should be parsed by openrouter model_1, no requests should go to cloudflare or openai
    assert openrouter_session._manager._failure_count["respond_with_429"].count > 0
    assert openrouter_session._manager._failure_count["respond_with_500"].count > 0
    assert openrouter_session._manager._failure_count["model_1"].count == 0
    assert openrouter_session._manager._failure_count["model_2"].count == 0

    assert cloudflare_ai_session._manager._failure_count["respond_with_429"].count == 0
    assert cloudflare_ai_session._manager._failure_count["respond_with_500"].count == 0
    assert cloudflare_ai_session._manager._failure_count["model_1"].count == 0
    assert cloudflare_ai_session._manager._failure_count["model_2"].count == 0

    assert openai_session._manager._failure_count["respond_with_429"].count == 0
    assert openai_session._manager._failure_count["respond_with_500"].count == 0
    assert openai_session._manager._failure_count["model_1"].count == 0
    assert openai_session._manager._failure_count["model_2"].count == 0


class WebhookDbData(TypedDict):
    espi_ebi: list[espi_ebi_models.EspiEbi]
    users: list[webhook_models.WebhookUser]
    endpoints: list[webhook_models.WebhookEndpoint]


@pytest.fixture(scope="function")
async def webhook_tests_db_data(db_session: AsyncSession) -> WebhookDbData:
    espi_ebi = [
        espi_ebi_models.EspiEbi(
            type="espi",
            title="title",
            description="description",
            company="company",
            source="source",
            date=datetime(year=2024, month=1, day=1),
        )
    ]
    db_session.add_all(espi_ebi)
    await db_session.flush()

    users = [
        webhook_models.WebhookUser(name=f"user{i}", api_key=f"api-key-{i}")
        for i in range(3)
    ]
    db_session.add_all(users)
    await db_session.flush()

    endpoints = [
        webhook_models.WebhookEndpoint(
            url="http://doesnt-exist", secret="secret", user_id=users[0].id
        ),
        webhook_models.WebhookEndpoint(
            url="http://127.0.0.1:6666/400", secret="secret", user_id=users[0].id
        ),
        webhook_models.WebhookEndpoint(
            url="http://127.0.0.1:6666/200", secret="secret", user_id=users[1].id
        ),
    ]

    db_session.add_all(endpoints)
    await db_session.commit()

    return {"espi_ebi": espi_ebi, "users": users, "endpoints": endpoints}


@patch("gpw_scraper.worker.create_pool")
async def test_dispatch_webhook_tasks(
    mock_create_pool, webhook_tests_db_data, db_sessionmaker, arq_pool: ArqRedis
):
    mock_pool = AsyncMock()
    mock_create_pool.return_value = mock_pool

    async def startup(ctx):
        ctx["db_sessionmaker"] = db_sessionmaker

    worker = Worker(
        on_startup=startup,
        functions=[dispatch_send_webhook_tasks],
        burst=True,
        poll_delay=0,
        queue_read_limit=10,
        redis_settings=settings.ARQ_REDIS_SETTINGS,
    )
    await arq_pool.enqueue_job(
        "dispatch_send_webhook_tasks", webhook_tests_db_data["espi_ebi"][0].id
    )
    await worker.main()

    assert mock_pool.enqueue_job.call_count == 3
    assert all(
        call.args[1] == webhook_tests_db_data["espi_ebi"][0]
        for call in mock_pool.enqueue_job.call_args_list
    )
    assert set(call.args[2].id for call in mock_pool.enqueue_job.call_args_list) == set(
        endpoint.id for endpoint in webhook_tests_db_data["endpoints"]
    )


@pytest.fixture
async def webhook_api():
    expected_webhook_body = {
        "id": 1,
        "type": "espi",
        "title": "title",
        "description": "description",
        "company": "company",
        "source": "source",
        "parsedByLlm": None,
        "date": "2024-01-01T00:00:00",
    }

    async def response_200(request: web.Request) -> web.Response:
        webhook_secret_header = request.headers["x-webhook-secret"]
        assert base64.b64decode(webhook_secret_header).decode("utf-8") == "secret"
        body = await request.json()
        assert body == expected_webhook_body

        if body["description"] == "FORCE_400":
            nonlocal force_fail_counter
            force_fail_counter += 1

            if force_fail_counter < 1:
                return web.HTTPBadRequest()

        return web.Response(body="ok", status=200)

    force_fail_counter = 0

    async def response_200_fail_first_time(request: web.Request) -> web.Response:
        nonlocal force_fail_counter

        if force_fail_counter < 1:
            force_fail_counter += 1
            return web.HTTPBadRequest()

        return await response_200(request)

    async def response_400(request: web.Request) -> web.Response:
        raise web.HTTPBadRequest()

    app = web.Application()
    app.router.add_post("/200", response_200)
    app.router.add_post("/200-fail-first-time", response_200_fail_first_time)
    app.router.add_post("/400", response_400)

    from aiohttp.test_utils import TestClient, TestServer

    client = TestClient(TestServer(app, port=6666))
    await client.start_server()

    yield

    await client.close()


async def test_send_webhook(
    webhook_api,
    webhook_tests_db_data,
    db_sessionmaker,
    db_session: AsyncSession,
    arq_pool: ArqRedis,
):
    async def startup(ctx):
        ctx["db_sessionmaker"] = db_sessionmaker

    worker = Worker(
        on_startup=startup,
        functions=[send_webhook],
        burst=True,
        poll_delay=0,
        queue_read_limit=10,
        redis_settings=settings.ARQ_REDIS_SETTINGS,
    )

    # dry run
    await arq_pool.enqueue_job(
        "send_webhook",
        webhook_tests_db_data["espi_ebi"][0],
        webhook_tests_db_data["endpoints"][0],
        dry_run=True,
    )
    await worker.main()

    event = (
        await db_session.execute(
            select(webhook_models.WebhookEvent)
            .order_by(webhook_models.WebhookEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    assert event.type == webhook_models.WebhookEventType.delivery_success
    assert event.http_code == 200
    assert event.meta == {"dry_run": True}

    # aiohttp.ClientResponseError
    await arq_pool.enqueue_job(
        "send_webhook",
        webhook_tests_db_data["espi_ebi"][0],
        webhook_tests_db_data["endpoints"][1],
    )
    await worker.main()
    event = (
        await db_session.execute(
            select(webhook_models.WebhookEvent)
            .order_by(webhook_models.WebhookEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    assert event.type == webhook_models.WebhookEventType.delivery_fail_response
    assert event.http_code == 400
    assert (
        event.meta is not None and event.meta["exception_type"] == "ClientResponseError"
    )

    # aiohttp.ClientError
    await arq_pool.enqueue_job(
        "send_webhook",
        webhook_tests_db_data["espi_ebi"][0],
        webhook_tests_db_data["endpoints"][0],
    )
    await worker.main()
    event = (
        await db_session.execute(
            select(webhook_models.WebhookEvent)
            .order_by(webhook_models.WebhookEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    assert event.type == webhook_models.WebhookEventType.delivery_fail
    assert event.http_code is None
    assert (
        event.meta is not None
        and event.meta["exception_type"] == "ClientConnectorError"
    )

    # Valid response
    await arq_pool.enqueue_job(
        "send_webhook",
        webhook_tests_db_data["espi_ebi"][0],
        webhook_tests_db_data["endpoints"][2],
    )
    await worker.main()
    event = (
        await db_session.execute(
            select(webhook_models.WebhookEvent)
            .order_by(webhook_models.WebhookEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one()
    assert event.type == webhook_models.WebhookEventType.delivery_success
    assert event.http_code == 200


async def test_send_webhook_retry_on_exception(
    webhook_api,
    webhook_tests_db_data,
    db_sessionmaker,
    db_session: AsyncSession,
    arq_pool: ArqRedis,
):
    async def startup(ctx):
        ctx["db_sessionmaker"] = db_sessionmaker

    endpoint = webhook_models.WebhookEndpoint(
        url="http://127.0.0.1:6666/200-fail-first-time",
        secret="secret",
        user_id=webhook_tests_db_data["users"][1].id,
    )
    db_session.add(endpoint)

    await db_session.commit()

    worker = Worker(
        on_startup=startup,
        functions=[send_webhook],
        burst=True,
        poll_delay=0,
        queue_read_limit=10,
        redis_settings=settings.ARQ_REDIS_SETTINGS,
    )

    await arq_pool.enqueue_job(
        "send_webhook",
        webhook_tests_db_data["espi_ebi"][0],
        endpoint,
    )
    await worker.main()
    events = (
        (
            await db_session.execute(
                select(webhook_models.WebhookEvent)
                .where(
                    webhook_models.WebhookEvent.espi_ebi_id
                    == webhook_tests_db_data["espi_ebi"][0].id
                )
                .order_by(webhook_models.WebhookEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    assert events[0].type == webhook_models.WebhookEventType.delivery_fail_response
    assert events[0].http_code == 400
    assert events[0].meta is not None

    assert events[1].type == webhook_models.WebhookEventType.delivery_success
    assert events[1].http_code == 200
