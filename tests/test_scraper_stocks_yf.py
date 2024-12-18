import os
from datetime import datetime

import pandas as pd
import pytest
from aiohttp import web
from zoneinfo import ZoneInfo

from gpw_scraper.models.stocks_ohlc import OHLCDataSource, StockOHLC
from gpw_scraper.scrapers.stocks.yf import YahooFinanceStocksScraper

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yf_html")


@pytest.fixture(scope="function")
async def yf_stocks_scraper(web_yahoo_finance) -> YahooFinanceStocksScraper:
    yf = YahooFinanceStocksScraper(web_yahoo_finance)
    return yf


@pytest.fixture(scope="function")
async def web_yahoo_finance(aiohttp_client):
    async def quote_history(request: web.Request):
        quote = request.match_info.get("quote")
        if quote is None:
            raise web.HTTPNotFound(reason="Quote not found in url")

        path = os.path.join(HTML_PATH, f"{quote}_history.html")
        if not os.path.exists(path):
            raise web.HTTPNotFound(reason=f"HTML page {path!s} not found")

        with open(path, "r") as file:
            return web.Response(body=file.read())

    app = web.Application()
    app.router.add_get("/quote/{quote}/history", quote_history)

    client = await aiohttp_client(app)
    setattr(client, "_base_url", "")
    yield client


async def test_get_historical_stocks_data(yf_stocks_scraper: YahooFinanceStocksScraper):
    expected = [
        StockOHLC(
            ticker="RKLB",
            open=25.95,
            high=26.26,
            low=24.53,
            close=26.01,
            date=pd.Timestamp("2024-12-17 00:00:00"),
            source=OHLCDataSource.YAHOO_FINANCE,
        ),
        StockOHLC(
            id=None,
            ticker="RKLB",
            open=27.98,
            high=28.10,
            low=21.87,
            close=25.90,
            date=pd.Timestamp("2024-12-01 00:00:00"),
            source=OHLCDataSource.YAHOO_FINANCE,
        ),
        StockOHLC(
            id=None,
            ticker="RKLB",
            open=10.90,
            high=28.05,
            low=10.85,
            close=27.28,
            date=pd.Timestamp("2024-11-01 00:00:00"),
            source=OHLCDataSource.YAHOO_FINANCE,
        ),
        StockOHLC(
            id=None,
            ticker="RKLB",
            open=9.66,
            high=12.09,
            low=8.80,
            close=10.70,
            date=pd.Timestamp("2024-10-01 00:00:00"),
            source=OHLCDataSource.YAHOO_FINANCE,
        ),
    ]
    result = await yf_stocks_scraper.get_historical_stocks_data("RKLB")

    assert len(result) == len(expected)
    for m1, m2 in zip(result, expected):
        assert all(
            getattr(m1, attr) == getattr(m2, attr)
            for attr in StockOHLC.__mapper__.columns.keys()
        )


async def test_get_historical_stocks_data_works_on_live_yf():
    expected = [
        StockOHLC(
            ticker="AAPL",
            open=179.61,
            high=180.17,
            low=174.64,
            close=174.92,
            date=pd.Timestamp("2022-01-05 00:00:00"),
            source=OHLCDataSource.YAHOO_FINANCE,
        ),
        StockOHLC(
            id=None,
            ticker="AAPL",
            open=182.63,
            high=182.94,
            low=179.12,
            close=179.70,
            date=pd.Timestamp("2022-01-04 00:00:00"),
            source=OHLCDataSource.YAHOO_FINANCE,
        ),
        StockOHLC(
            id=None,
            ticker="AAPL",
            open=177.83,
            high=182.88,
            low=177.71,
            close=182.01,
            date=pd.Timestamp("2022-01-03 00:00:00"),
            source=OHLCDataSource.YAHOO_FINANCE,
        ),
    ]
    yf = YahooFinanceStocksScraper.with_default_session()
    result = await yf.get_historical_stocks_data(
        "AAPL",
        frequency="1d",
        start_date=datetime(year=2022, month=1, day=1, tzinfo=ZoneInfo("Etc/UTC")),
        end_date=datetime(year=2022, month=1, day=6, tzinfo=ZoneInfo("Etc/UTC")),
    )
    assert len(result) == len(expected)
    for m1, m2 in zip(result, expected):
        assert all(
            getattr(m1, attr) == getattr(m2, attr)
            for attr in StockOHLC.__mapper__.columns.keys()
        )


async def test_get_historical_stocks_data_include_currency(
    yf_stocks_scraper: YahooFinanceStocksScraper,
):
    _, currency = await yf_stocks_scraper.get_historical_stocks_data(
        "XTB.WA", include_currency=True
    )
    assert currency == "PLN"


async def test_get_ticker_ohlc_for_date(
    yf_stocks_scraper: YahooFinanceStocksScraper,
):
    expected = StockOHLC(
        id=None,
        ticker="LUNR",
        open=12.92,
        high=14.1,
        low=12.67,
        close=14.06,
        date=pd.Timestamp("2024-12-17 00:00:00"),
        source=OHLCDataSource.YAHOO_FINANCE,
        created_at=None,
    )
    result = await yf_stocks_scraper.get_ticker_ohlc_for_date(
        "LUNR", dt=datetime(year=2024, month=12, day=10, tzinfo=ZoneInfo("Etc/UTC"))
    )
    assert all(
        getattr(result, attr) == getattr(expected, attr)
        for attr in StockOHLC.__mapper__.columns.keys()
    )


async def test_get_ticker_ohlc_for_date_raise_if_not_exact_date(
    yf_stocks_scraper: YahooFinanceStocksScraper,
):
    with pytest.raises(ValueError, match=r"Data for .* at .* not found"):
        await yf_stocks_scraper.get_ticker_ohlc_for_date(
            "XTB.WA",
            dt=datetime(year=2024, month=12, day=10, tzinfo=ZoneInfo("Etc/UTC")),
        )
