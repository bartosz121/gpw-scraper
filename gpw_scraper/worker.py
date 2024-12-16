import asyncio
import base64
from datetime import datetime

import aiohttp
import redis.asyncio as redis
from arq import Retry, create_pool, cron
from arq.cron import CronJob
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gpw_scraper.config import settings
from gpw_scraper.databases.db import sessionmaker
from gpw_scraper.llm import LLMClientManaged, ModelManager
from gpw_scraper.models.espi_ebi import EspiEbi
from gpw_scraper.models.webhook import WebhookEndpoint, WebhookEvent, WebhookEventType
from gpw_scraper.schemas.espi_ebi import EspiEbiItem
from gpw_scraper.scrapers.pap import EspiEbiPapScraper, PapHrefItem
from gpw_scraper.services.espi_ebi import SQLAEspiEbiService
from gpw_scraper.services.sqlalchemy import ConflictError
from gpw_scraper.services.webhook import (
    SQLAWebhookEndpointService,
    SQLAWebhookEventService,
)


async def scrape_pap_espi_ebi(ctx, date_start: datetime, date_end: datetime):
    pool = await create_pool(settings.ARQ_REDIS_SETTINGS)
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
        else:
            await pool.enqueue_job("dispatch_send_webhook_tasks", item.id)

        await espi_ebi_service.session.close()


async def cron_scrape_pap_espi_ebi(ctx):
    await scrape_pap_espi_ebi(ctx, datetime.now(), datetime.now())


async def dispatch_send_webhook_tasks(ctx, espi_ebi_entry_id: int):
    pool = await create_pool(settings.ARQ_REDIS_SETTINGS)
    db_sessionmaker: async_sessionmaker[AsyncSession] = ctx["db_sessionmaker"]

    async with db_sessionmaker() as session:
        espi_ebi_service = SQLAEspiEbiService(session)
        endpoint_service = SQLAWebhookEndpointService(session)

        espi_ebi = await espi_ebi_service.get(id=espi_ebi_entry_id)
        endpoints = await endpoint_service.list_()
        logger.info(f"Queuing {len(endpoints)} webhook messages to be sent")
        for endpoint in endpoints:
            logger.error(settings.ENVIRONMENT.is_qa)
            await pool.enqueue_job(
                "send_webhook", espi_ebi, endpoint, dry_run=settings.ENVIRONMENT.is_qa
            )


async def send_webhook(
    ctx, espi_ebi: EspiEbi, endpoint: WebhookEndpoint, *, dry_run: bool = False
):
    db_sessionmaker: async_sessionmaker[AsyncSession] = ctx["db_sessionmaker"]
    async with db_sessionmaker() as session:
        event_service = SQLAWebhookEventService(session)
        payload = EspiEbiItem.model_validate(espi_ebi).model_dump(
            mode="json", by_alias=True
        )
        event = WebhookEvent(webhook_id=endpoint.id, espi_ebi_id=espi_ebi.id)
        retry_job = False

        async with aiohttp.ClientSession() as client:
            try:
                if dry_run:
                    logger.info(
                        f"Would have sent espi ebi #{espi_ebi.id} payload to {endpoint.url!s}"
                    )
                    event.meta = {"dry_run": True}
                    response_status = 200
                else:
                    b64_secret = base64.b64encode(
                        endpoint.secret.encode("utf-8")
                    ).decode("utf-8")
                    # TODO: .post should be used as context manager
                    response = await client.post(
                        endpoint.url,
                        json=payload,
                        headers={
                            "user-agent": "gpw-scraper webhook",
                            "x-webhook-secret": b64_secret,
                        },
                        timeout=aiohttp.ClientTimeout(60),
                    )
                    response_text = await response.text()
                    response_status = response.status
                    response.raise_for_status()
                    response_status = response.status
            except aiohttp.ClientResponseError as exc:
                retry_job = True
                event.http_code = exc.status
                logger.error(f"Response error: {exc!s}")
                event.type = WebhookEventType.delivery_fail_response
                event.meta = {
                    "exception_type": type(exc).__name__,
                    "response_text": response_text,  # type: ignore mute unbound error because of aiohttp weirdness if not used as context manager
                    "exception": str(exc),
                }
            except aiohttp.ClientError as exc:
                retry_job = True
                logger.error(f"Connection error: {exc!s}")
                event.type = WebhookEventType.delivery_fail
                event.meta = {
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                }
            except Exception as exc:
                retry_job = True
                logger.error(f"Exception: {exc!s}")
                event.type = WebhookEventType.delivery_fail
                event.meta = {
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                }
            else:
                logger.info("Response status ok")
                event.http_code = response_status
                event.type = WebhookEventType.delivery_success
            finally:
                logger.debug(f"Saving webhook event {event!r}")
                await event_service.create(event, auto_commit=True)

                if retry_job:
                    logger.info(f"Retrying job for #{espi_ebi.id}")
                    raise Retry(defer=ctx["job_try"] * 5)


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
    await ctx["openrouter_session"].close()
    await ctx["cloudflare_ai_session"].close()
    await ctx["openai_session"].close()


class WorkerSettings:
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = settings.ARQ_REDIS_SETTINGS
    max_tries = 3
    retry_jobs = True
    functions = [scrape_pap_espi_ebi, dispatch_send_webhook_tasks, send_webhook]
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
