import asyncio
from datetime import datetime

import aiohttp
import redis.asyncio as redis
from arq import cron
from arq.cron import CronJob
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gpw_scraper.config import settings
from gpw_scraper.databases.db import sessionmaker
from gpw_scraper.llm import LLMClientManaged, ModelManager
from gpw_scraper.scrapers.pap import EspiEbiPapScraper, PapHrefItem
from gpw_scraper.services.espi_ebi import SQLAEspiEbiService
from gpw_scraper.services.sqlalchemy import ConflictError


async def scrape_pap_espi_ebi(ctx, date_start: datetime, date_end: datetime):
    scraper = EspiEbiPapScraper()
    redis_client: redis.Redis = ctx["redis_client"]
    pap_session: aiohttp.ClientSession = ctx["pap_session"]
    openrouter_session: LLMClientManaged = ctx["openrouter_session"]
    cloudflare_ai_session: LLMClientManaged = ctx["cloudflare_ai_session"]
    openai_session: LLMClientManaged = ctx["openai_session"]
    db_sessionmaker: async_sessionmaker[AsyncSession] = ctx["db_sessionmaker"]

    espi_ebi_service = SQLAEspiEbiService(session=db_sessionmaker())

    already_in_db_at_date_range = await espi_ebi_service.list_in_date_range(
        date_start, date_end
    )
    ignore_list = [
        item.source[item.source.rindex("node") - 1 :]
        for item in already_in_db_at_date_range
    ]

    logger.info(f"{ignore_list=}")

    hrefs = await scraper.scrape_hrefs_in_range(pap_session, date_start, date_end)

    filtered_hrefs: list[PapHrefItem] = []

    for href_item in hrefs:
        logger.debug(
            f"{href_item.href} Checking if item is in ignore list or in progress"
        )
        if href_item.href not in ignore_list:
            logger.debug(f"{href_item.href} Not in ignore list")

            if (await redis_client.get(href_item.href)) is None:
                logger.debug(f"{href_item.href} Not in progress")
                await redis_client.set(href_item.href, 1, 600)
                filtered_hrefs.append(href_item)
            else:
                logger.debug(f"{href_item.href} Is in progress, skipping")
        else:
            logger.debug(f"{href_item.href} Is in ignore list, skipping")

    for task in asyncio.as_completed(
        [
            scraper.scrape_item_data(
                pap_session,
                href,
                [openrouter_session, cloudflare_ai_session, openai_session],
            )
            for href in filtered_hrefs
        ]
    ):
        item = await task
        logger.info(f"{item.source} done")
        logger.info(f"Adding {item.source} to db")
        try:
            await espi_ebi_service.create(item, auto_commit=True)
        except ConflictError as exc:
            logger.error(str(exc))
        try:
            await espi_ebi_service.create(item, auto_commit=True)
        except ConflictError as exc:
            logger.error(str(exc))

        await espi_ebi_service.session.close()


async def cron_scrape_pap_espi_ebi(ctx):
    await scrape_pap_espi_ebi(ctx, datetime.now(), datetime.now())


async def startup(ctx):
    ctx["redis_client"] = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )
    ctx["pap_session"] = aiohttp.ClientSession(base_url=EspiEbiPapScraper.url)
    ctx["openrouter_session"] = LLMClientManaged(
        settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
        chat_completion_path=settings.OPENROUTER_URL_PATH,
        manager=ModelManager(
            models=settings.OPENROUTER_MODEL_LIST,
            model_index_reset_delta=settings.MODEL_MANAGER_INDEX_RESET_DELTA,
        ),
    )
    ctx["cloudflare_ai_session"] = LLMClientManaged(
        settings.CLOUDFLARE_AI_BASE_URL,
        api_key=settings.CLOUDFLARE_AI_API_KEY,
        chat_completion_path=settings.CLOUDFLARE_AI_URL_PATH,
        manager=ModelManager(
            models=settings.CLOUDFLARE_AI_MODEL_LIST,
            model_index_reset_delta=settings.MODEL_MANAGER_INDEX_RESET_DELTA,
        ),
    )
    ctx["openai_session"] = LLMClientManaged(
        settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        chat_completion_path=settings.OPENAI_AI_URL_PATH,
        manager=ModelManager(
            models=settings.OPENAI_MODELS_LIST,
            model_index_reset_delta=settings.MODEL_MANAGER_INDEX_RESET_DELTA,
        ),
    )
    ctx["db_sessionmaker"] = sessionmaker


async def shutdown(ctx):
    await ctx["redis_client"].aclose()
    await ctx["pap_session"].close()
    await ctx["pap_session"].close()
    await ctx["openrouter_session"].close()
    await ctx["cloudflare_ai_session"].close()
    await ctx["openai_session"].close()
    await ctx["db_sessionmaker"].close()


class WorkerSettings:
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = settings.ARQ_REDIS_SETTINGS
    functions = [scrape_pap_espi_ebi]
    cron_jobs: list[CronJob] | None = (
        None
        if settings.ENVIRONMENT.is_qa
        else [
            cron(
                cron_scrape_pap_espi_ebi,
                minute=set(range(0, 60, 5)),  # every 5 min
                max_tries=1,
                timeout=500,
            ),
        ]
    )
