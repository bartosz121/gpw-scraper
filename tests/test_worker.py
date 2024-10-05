from datetime import datetime

from arq.connections import ArqRedis
from arq.worker import Worker
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gpw_scraper.config import settings
from gpw_scraper.llm import LLMClientManaged, ModelManager
from gpw_scraper.worker import scrape_pap_espi_ebi


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
