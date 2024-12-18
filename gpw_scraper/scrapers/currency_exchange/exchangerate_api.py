from typing import ClassVar

import aiohttp


class ExchangeRateApi:
    BASE_URL: ClassVar[str] = "https://v6.exchangerate-api.com/v6"

    @staticmethod
    async def get_latest_exchange_rate(
        api_key: str, *, base_code: str = "PLN", base_url: str | None = None
    ) -> dict[str, float]:
        if base_url is None:
            base_url = ExchangeRateApi.BASE_URL

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/{api_key}/latest/{base_code}"
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data["conversion_rates"]
