import io
from datetime import datetime, timedelta
from typing import Literal, overload

import aiohttp
import pandas as pd
from loguru import logger

from gpw_scraper import utils
from gpw_scraper.beautifulsoup import BeautifulSoup
from gpw_scraper.models.stocks_ohlc import OHLCDataSource, StockOHLC


class YahooFinanceStocksScraper:
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
    def with_default_session(cls) -> "YahooFinanceStocksScraper":
        headers = utils.get_random_headers()
        session = aiohttp.ClientSession(base_url=cls._base_url, headers=headers)
        return cls(session)

    @overload
    async def get_historical_stocks_data(
        self,
        quote: str,
        *,
        frequency: Literal["1d", "1wk", "1mo"] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_currency: Literal[False] = False,
    ) -> list[StockOHLC]: ...

    @overload
    async def get_historical_stocks_data(
        self,
        quote: str,
        *,
        frequency: Literal["1d", "1wk", "1mo"] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_currency: Literal[True] = True,
    ) -> tuple[list[StockOHLC], str]: ...

    async def get_historical_stocks_data(
        self,
        quote: str,
        *,
        frequency: Literal["1d", "1wk", "1mo"] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_currency=False,
    ) -> list[StockOHLC] | tuple[list[StockOHLC], str]:
        url = f"/quote/{quote}/history"
        params = self._google_translate_params.copy()

        if start_date:
            params["period1"] = int(start_date.timestamp())

        if end_date:
            params["period2"] = int(end_date.timestamp())

        if frequency:
            params["frequency"] = frequency

        logger.info(f"Fetching historical yf {quote!s} data {url=}, {params=}")
        r = await self.session.get(url, params=params, allow_redirects=True)
        r.raise_for_status()
        body = await r.text()

        soup = BeautifulSoup(body, features="html.parser")
        currency = (
            soup.yf_historical_data_get_currency() or "USD"
        )  # FIXME: USD as default, trashy but need it for now
        logger.debug(f"{quote!s} ohlc currency: {currency!s}")

        try:
            tables = pd.read_html(io.StringIO(body), flavor="bs4")
            logger.debug(f"{tables=}")
        except ValueError as exc:
            logger.error(f"No html table found in {self._base_url}{url}")
            raise exc

        df = tables[0]

        # Cleanup dataframe, parse date to python, change "Close*" column name to just "Close"
        df["Date"] = pd.to_datetime(df["Date"], format="%b %d, %Y")
        df.rename(
            columns={df.columns[df.columns.str.startswith("Close")][0]: "Close"},
            inplace=True,
        )

        # To db model
        ohlc: list[StockOHLC] = []

        for _, row in df.iterrows():
            if isinstance(row.Open, str) and "dividend" in row.Open.lower():
                continue

            ohlc_item = StockOHLC(
                ticker=quote,
                open=row.Open,
                high=row.High,
                low=row.Low,
                close=row.Close,
                date=row.Date,
                source=OHLCDataSource.YAHOO_FINANCE,
            )
            ohlc.append(ohlc_item)

        return (ohlc, currency) if include_currency else ohlc

    async def get_ticker_ohlc_for_date(
        self,
        ticker: str,
        dt: datetime,
        *,
        raise_if_not_exact_date: bool = False,
    ) -> StockOHLC:
        start_date = dt.replace(hour=0, minute=0, second=0)
        end_date = start_date + timedelta(days=1)
        data = await self.get_historical_stocks_data(
            ticker,
            frequency="1d",
            start_date=start_date,
            end_date=end_date,
            include_currency=False,
        )
        logger.debug(f"{data=}")

        if len(data) != 1:
            raise ValueError(f"Data for {ticker!s} at {dt!s} not found")
        if len(data) > 1:
            raise ValueError(f"Unexpected data for {ticker!s} at {dt!s}")

        ohlc = data.pop()

        if raise_if_not_exact_date:
            if ohlc.date.date() != dt.date():
                raise ValueError("Found OHLC date is not equal to target date")

        return ohlc
