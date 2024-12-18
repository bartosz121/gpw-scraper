import aiohttp
from loguru import logger

from gpw_scraper import utils
from gpw_scraper.beautifulsoup import BeautifulSoup
from gpw_scraper.models.tickers_metadata import TickerMetadata


class YahooFinanceTickersMetadataScraper:
    _base_url = "https://finance-yahoo-com.translate.goog"
    _google_translate_params: dict[str, str | int] = {
        "_x_tr_sl": "pl",
        "_x_tr_tl": "en",
        "_x_tr_hl": "pl",
        "_x_tr_pto": "wapp",
    }

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    @classmethod
    def with_default_session(cls) -> "YahooFinanceTickersMetadataScraper":
        headers = utils.get_random_headers()
        session = aiohttp.ClientSession(base_url=cls._base_url, headers=headers)
        return cls(session)

    async def get_ticker_metadata(self, ticker: str) -> TickerMetadata:
        url = f"/quote/{ticker}/profile"
        logger.debug(f"{url=} {self._google_translate_params=}")
        r = await self.session.get(
            url, params=self._google_translate_params, allow_redirects=True
        )
        r.raise_for_status()
        body = await r.text()

        soup = BeautifulSoup(body, features="html.parser")

        company_name = soup.yf_profile_get_company_name()
        if company_name is None:
            raise ValueError(f"Company name not found in yf {ticker!s} profile")

        currency = soup.yf_profile_get_currency()
        if currency is None:
            raise ValueError(f"Currency not found in yf {ticker!s} profile")

        sector = soup.yf_profile_get_sector()
        if sector is None:
            raise ValueError(f"Sector not found in yf {ticker!s} profile")

        industry = soup.yf_profile_get_industry()
        if industry is None:
            raise ValueError(f"Industry not found in yf {ticker!s} profile")

        description = soup.yf_profile_get_description(cleanup=True)

        return TickerMetadata(
            ticker=ticker,
            currency_symbol=currency,
            full_name=company_name,
            sector=sector,
            industry=industry,
            description=description,
        )
