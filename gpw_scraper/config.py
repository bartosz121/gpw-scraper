from enum import StrEnum
from typing import Literal, NamedTuple

from arq.connections import RedisSettings
from pydantic import SecretStr, computed_field
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMArgs(NamedTuple):
    url: str
    model: str


LLM_PROVIDERS = Literal["CLOUDFLARE", "OPENROUTER", "OPENAI"]


class Environment(StrEnum):
    TESTING = "TESTING"
    LOCAL = "LOCAL"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"

    @property
    def is_testing(self) -> bool:
        return self == Environment.TESTING

    @property
    def is_development(self) -> bool:
        return self == Environment.LOCAL

    @property
    def is_staging(self) -> bool:
        return self == Environment.STAGING

    @property
    def is_qa(self) -> bool:
        return self in {
            Environment.TESTING,
            Environment.LOCAL,
            Environment.STAGING,
        }

    @property
    def is_production(self) -> bool:
        return self == Environment.PRODUCTION


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ENVIRONMENT: Environment = Environment.LOCAL
    LOG_LEVEL: str = "DEBUG"

    EXCHANGERATE_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai"
    OPENROUTER_URL_PATH: str = "/api/v1/chat/completions"
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL_LIST: list[str] = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "meta-llama/llama-3-8b-instruct:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "google/gemma-2-9b-it:free",
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.2-3b-instruct",
    ]

    CLOUDFLARE_AI_BASE_URL: str = "https://api.cloudflare.com"

    @computed_field
    @property
    def CLOUDFLARE_AI_URL_PATH(self) -> str:
        return f"/client/v4/accounts/{self.CLOUDFLARE_AI_ACCOUNT_ID}/ai/v1/chat/completions"

    CLOUDFLARE_AI_API_KEY: str
    CLOUDFLARE_AI_ACCOUNT_ID: str
    CLOUDFLARE_AI_MODEL_LIST: list[str] = [
        "@cf/meta/llama-3.1-70b-instruct",
        "@cf/meta/llama-3-8b-instruct-awq",
        "@cf/meta/llama-3.1-8b-instruct",
        "@cf/meta/llama-3.1-8b-instruct-fp8",
        "@cf/meta/llama-3.1-8b-instruct-awq",
        "@cf/meta/llama-3-8b-instruct",
        "@cf/meta/llama-3.2-3b-instruct",
        "@cf/meta/llama-3.2-1b-instruct",
    ]

    OPENAI_BASE_URL: str = "https://api.openai.com"
    OPENAI_AI_URL_PATH: str = "/v1/chat/completions"
    OPENAI_API_KEY: str
    OPENAI_MODELS_LIST: list[str] = ["gpt-4o-mini"]

    LLM_PROVIDER: LLM_PROVIDERS = "OPENROUTER"
    LLM_PROVIDER_FALLBACK: LLM_PROVIDERS = "OPENAI"
    MODEL_MANAGER_INDEX_RESET_DELTA: float = 600

    DB_SCHEME: str
    DB_HOST: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: SecretStr | None = None
    DB_DATABASE: str
    DB_PORT: int | None = None

    REDIS_HOST: str
    REDIS_PASSWORD: str | None = None
    REDIS_PORT: int

    @computed_field
    @property
    def DB_URL(self) -> str:
        return MultiHostUrl.build(
            scheme=self.DB_SCHEME,
            username=self.DB_USER,
            password=self.DB_PASSWORD.get_secret_value()
            if isinstance(self.DB_PASSWORD, SecretStr)
            else None,
            host=self.DB_HOST,
            port=self.DB_PORT,
            path=self.DB_DATABASE,
        ).unicode_string()

    @computed_field
    @property
    def ARQ_REDIS_SETTINGS(self) -> RedisSettings:
        return RedisSettings(
            self.REDIS_HOST,
            self.REDIS_PORT,
            password=self.REDIS_PASSWORD,
        )


settings = Settings()  # type: ignore
