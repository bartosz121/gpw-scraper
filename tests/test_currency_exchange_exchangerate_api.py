from gpw_scraper.config import settings
from gpw_scraper.scrapers.currency_exchange.exchangerate_api import ExchangeRateApi


async def test_currency_exchange_exchangerate_api_live():
    data = await ExchangeRateApi.get_latest_exchange_rate(
        settings.EXCHANGERATE_API_KEY, base_code="PLN"
    )
    assert len(data) > 0
