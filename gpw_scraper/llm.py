import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypedDict, assert_never

import aiohttp
import pydantic
from loguru import logger

from gpw_scraper.schemas.espi_ebi import EspiLLMSummary

ESPI_DESCRIPTION = """ESPI, or the Electronic Information Transmission System, is a platform used by public companies in Poland
 to disclose important regulatory information to the market. It is similar to the SEC's EDGAR system in the United States.
 Companies use ESPI to submit financial reports, corporate governance updates, material events,
 and other legally required documents to the Warsaw Stock Exchange and make them accessible to investors and the public.
"""  # noqa: E501

SYSTEM_PROMPT = f"""You are an AI assistant specialized in extracting and summarizing information from ESPI report HTML pages.
{ESPI_DESCRIPTION}.
Your task is to analyze HTML content, extract relevant information, and format it according to a specific JSON schema.
Focus on identifying the report's title and summarizing its content while adhering to given guidelines.
Do not include information about HTML structure, ESPI, or PAP in your summary, and exclude company-specific details like address, NIP, or REGON from the description.
"""  # noqa: E501

TASK_PROMPT = """Extract and summarize information from the following ESPI report HTML page. Follow these steps:

1. Extract the title:
   - Look for a table row (<tr>) containing a cell (<td>) with the text "Tytuł".
   - If found, use the content of the adjacent cell as the title.
   - If not found, read the entire report and create a concise title based on its content.

2. Extract the report content:
   - Search for a table cell (<td>) with the text "Treść raportu:".
   - If found, use the content that follows as the report content.
   - If not found, consider the entire page content as the report.

3. Summarize the report content to create a title and description

4. Format your response to match the following JSON schema: {json_schema}

Ensure the title is short, concise, and does not contain company information. The description should summarize the key points of the report without including company-specific details.

Your response must be a stringified json as it will be parsed by automated function and every other response will be invalid.

Don't wrap your response with markdown formatting.

Now, analyze the following HTML content and provide the extracted information in the specified JSON format:

```
{html_content}
```

Title and description must be in polish, create it in polish in the first place or translate it.
"""  # noqa: E501


@dataclass
class ModelFailure:
    count: int = 0
    last_report: datetime | None = None

    def last_report_delta(self) -> timedelta | None:
        return None if self.last_report is None else datetime.now(tz=UTC) - self.last_report

    def reset(self) -> None:
        self.count = 0
        self.last_report = None


class NoMoreModelsAvailableError(Exception): ...


class ModelManager:
    _models: list[str]
    _failure_count: dict[str, ModelFailure]
    _failure_threshold: int
    _failure_reset_delta: float
    _model_index_reset_delta: float
    _current_model_index: int
    _lock: asyncio.Lock

    def __init__(
        self,
        models: list[str],
        *,
        failure_threshold: int = 3,
        failure_count_reset_delta: float = 60.0,
        model_index_reset_delta: float = 300.0,
    ) -> None:
        if len(models) < 1:
            msg = "You must provide atleast one model"
            raise ValueError(msg)

        self._models = models
        self._current_model_index = 0
        self._failure_count = {model: ModelFailure() for model in self._models}
        self._failure_threshold = failure_threshold
        self._failure_reset_delta = failure_count_reset_delta
        self._model_index_reset_delta = model_index_reset_delta
        self._lock = asyncio.Lock()

    @property
    async def model(self) -> str:
        await self._check_current_state()

        async with self._lock:
            model_ = self._models[self._current_model_index]
            return model_

    async def _check_current_state(self) -> None:
        async with self._lock:
            initial_index = self._current_model_index

            if (
                first_model_delta := self._failure_count[self._models[0]].last_report_delta()
            ) and first_model_delta.total_seconds() >= self._model_index_reset_delta:
                logger.debug(
                    f"First model last report delta ({first_model_delta}) >= model index delta, reseting model failures"
                )
                self._current_model_index = 0
                for model in self._failure_count.keys():  # noqa: SIM118
                    self._failure_count[model].reset()
                return

            while True:
                model = self._models[self._current_model_index]
                if self._failure_count[model].count < self._failure_threshold:
                    break

                self._current_model_index = (self._current_model_index + 1) % len(self._models)

                if self._current_model_index == initial_index:
                    raise NoMoreModelsAvailableError()

    async def report_model_failure(self, model: str) -> None:
        async with self._lock:
            try:
                if (
                    delta := self._failure_count[model].last_report_delta()
                ) and delta.total_seconds() < self._failure_reset_delta:
                    self._failure_count[model].count += 1
                else:
                    self._failure_count[model].count = 1

                self._failure_count[model].last_report = datetime.now(tz=UTC)
            except KeyError as exc:
                msg = f"Model {model!r} not found"
                raise ValueError(msg) from exc


class ChatCompletionMessage(TypedDict):
    role: str
    content: str


class LLMClient:
    _client: aiohttp.ClientSession
    _api_key: str
    _chat_completion_path: str

    def __init__(
        self,
        base_url: str,
        chat_completion_path: str,
        api_key: str,
    ) -> None:
        self._api_key = api_key
        self._chat_completion_path = chat_completion_path
        self._client = aiohttp.ClientSession(
            base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        logger.debug("__aexit__ closing client")
        await self._client.close()

    async def close(self):
        await self._client.close()

    def __del__(self):
        if not self._client.closed:
            logger.debug("__del__ closing client")
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(self._client.close())
            else:
                asyncio.run(self._client.close())

    async def _chat_completion(self, model: str, messages: list[ChatCompletionMessage]) -> aiohttp.ClientResponse:
        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        response = await self._client.post(self._chat_completion_path, json=payload)
        return response

    def _create_espi_summary_messages(self, page_content: str) -> list[ChatCompletionMessage]:  # noqa: PLR6301
        return [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": TASK_PROMPT.format(
                    json_schema=json.dumps(EspiLLMSummary.model_json_schema()),
                    html_content=page_content,
                ),
            },
        ]

    async def get_espi_summary(self, model: str, page_content: str) -> tuple[EspiLLMSummary, str]:
        """
        tuple[EspiLLMSummary, str] -> EspiLLMSummary, used model
        """
        messages = self._create_espi_summary_messages(page_content)
        response = await self._chat_completion(model, messages)
        response.raise_for_status()
        data = await response.json()
        logger.debug(data)

        llm_summary = EspiLLMSummary.model_validate_json(data["choices"][0]["message"]["content"])
        return llm_summary, model

    @staticmethod
    def is_llm_espi_summary_valid(item: EspiLLMSummary) -> bool:
        """
        Sanity check for LLM response
        """
        return "Summary of the ESPI report" not in item.description


class LLMClientManaged(LLMClient):
    _manager: ModelManager

    def __init__(
        self,
        base_url: str,
        chat_completion_path: str,
        api_key: str,
        *,
        manager: ModelManager,
    ) -> None:
        super().__init__(base_url, chat_completion_path, api_key)
        self._manager = manager

    async def get_espi_summary_until_valid(
        self,
        page_content: str,
        *,
        tries_per_model: int = 3,
        sleep_on_failure: bool = True,
        sleep_amount: int = 5,
    ) -> tuple[EspiLLMSummary, str] | None:
        page_hash = hashlib.blake2b(page_content.encode()).hexdigest()[:10]
        try:
            while True:
                model = await self._manager.model
                logger.debug(model)

                for _ in range(tries_per_model):
                    check_model = await self._manager.model
                    if check_model != model:
                        logger.debug(f"[{page_hash}] new model from manager: {model} -> {check_model}")
                        break
                    logger.debug(f"[{page_hash}] trying {model} for {_} time")
                    try:
                        result = await self.get_espi_summary(model, page_content)
                    except pydantic.ValidationError:
                        logger.warning(f"[{page_hash}] pydantic validation error")
                        if sleep_on_failure:
                            logger.info(f"[{page_hash}] sleeping for {sleep_amount}s")
                            await asyncio.sleep(sleep_amount)
                    except (
                        aiohttp.ServerConnectionError,
                        aiohttp.ClientResponseError,
                    ) as exc:
                        logger.warning(f"[{page_hash}] aiohttp error: {exc!s}")
                        await self._manager.report_model_failure(model)
                        if sleep_on_failure:
                            logger.info(f"[{page_hash}] sleeping for {sleep_amount}s")
                            await asyncio.sleep(sleep_amount)
                        continue
                    else:
                        if not LLMClient.is_llm_espi_summary_valid(result[0]):
                            logger.debug(f"[{page_hash}] LLM respone not valid, trying again")
                            continue

                        logger.debug(f"[{page_hash}] Received valid LLM response")
                        return result
                else:
                    # TODO: skip model at this point
                    await self._manager.report_model_failure(model)
        except NoMoreModelsAvailableError:
            return None
        else:
            assert_never(page_content)
