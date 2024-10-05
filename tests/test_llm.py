import asyncio

import aiohttp
import aiohttp.test_utils

from gpw_scraper.llm import LLMClientManaged, ModelManager


async def test_model_manager():
    models = ["error_1", "error_2", "error_3", "model_1"]
    manager = ModelManager(models, failure_threshold=3)

    async def fn():
        model = await manager.model
        if model.startswith("error"):
            await manager.report_model_failure(model)
        else:
            return None

    assert await manager.model == models[0]

    await fn()
    await fn()
    await fn()
    assert await manager.model == models[1]

    await asyncio.gather(*(fn() for _ in range(100)))

    assert await manager.model == models[-1]


async def test_model_manager_failure_reset_delta_resets_failure_count():
    models = ["error_1", "model_1"]
    manager = ModelManager(
        models,
        failure_threshold=3,
        failure_count_reset_delta=2.0,
    )

    async def fn():
        model = await manager.model
        if model.startswith("error"):
            await manager.report_model_failure(model)
        else:
            return None

    assert await manager.model == models[0]
    await fn()
    await fn()
    assert manager._failure_count["error_1"].count == 2

    await asyncio.sleep(2.5)
    await fn()

    assert manager._failure_count["error_1"].count == 1


async def test_llm_client_model_manager_get_espi_summary_until_valid(
    llm_rest_api_client: aiohttp.test_utils.TestClient,
):
    models = ["respond_with_429", "respond_with_500", "respond_with_429", "valid"]
    manager = ModelManager(models, failure_threshold=5, failure_count_reset_delta=5.0)
    async with LLMClientManaged(
        base_url="http://localhost",
        chat_completion_path="/api/v1/chat/completions",
        api_key="",
        manager=manager,
    ) as client:
        client._client = llm_rest_api_client  # type: ignore

        tasks = [client.get_espi_summary_until_valid("") for _ in range(500)]

        results = await asyncio.gather(*tasks)

        assert all(result is not None and result[1] == "valid" for result in results)


async def test_llm_client_manager_get_espi_summary_until_valid_returns_none_if_all_models_bad(
    llm_rest_api_client: aiohttp.test_utils.TestClient,
):
    models = [
        "respond_with_429",
        "respond_with_500",
        "respond_with_429",
        "respond_with_500",
    ]
    manager = ModelManager(models, failure_threshold=2)
    async with LLMClientManaged(
        base_url="http://localhost",
        chat_completion_path="/api/v1/chat/completions",
        api_key="",
        manager=manager,
    ) as client:
        client._client = llm_rest_api_client  # type: ignore

        tasks = [client.get_espi_summary_until_valid("") for _ in range(500)]

        results = await asyncio.gather(*tasks)

        assert all(result is None for result in results)


async def test_model_manager_model_index_reset_delta():
    models = ["a", "b", "c", "d", "e"]
    manager = ModelManager(
        models,
        failure_threshold=1,
        failure_count_reset_delta=1,
        model_index_reset_delta=5.0,
    )

    await manager.report_model_failure(models[0])
    await manager.report_model_failure(models[0])
    assert await manager.model == models[1]

    await manager.report_model_failure(models[1])
    await manager.report_model_failure(models[1])
    assert await manager.model == models[2]

    await asyncio.sleep(5.5)

    assert await manager.model == models[0]
