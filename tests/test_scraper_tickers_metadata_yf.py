import os

import pytest
from aiohttp import web

from gpw_scraper.models.tickers_metadata import TickerMetadata
from gpw_scraper.scrapers.tickers_metadata.yf import YahooFinanceTickersMetadataScraper

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yf_html")


@pytest.fixture(scope="function")
async def web_yahoo_finance_quote_profile(aiohttp_client):
    async def quote_profile(request: web.Request):
        quote = request.match_info.get("quote")
        if quote is None:
            raise web.HTTPNotFound(reason="Quote not found in url")

        path = os.path.join(HTML_PATH, f"{quote}_profile.html")
        if not os.path.exists(path):
            raise web.HTTPNotFound(reason=f"HTML page {path!s} not found")

        with open(path, "r") as file:
            return web.Response(body=file.read())

    app = web.Application()
    app.router.add_get("/quote/{quote}/profile", quote_profile)

    client = await aiohttp_client(app)
    setattr(client, "_base_url", "")
    yield client


@pytest.fixture(scope="function")
async def yf_tickers_metadata_scraper(
    web_yahoo_finance_quote_profile,
) -> YahooFinanceTickersMetadataScraper:
    yf = YahooFinanceTickersMetadataScraper(web_yahoo_finance_quote_profile)
    return yf


async def test_get_ticker_company_full_name_and_description(
    yf_tickers_metadata_scraper: YahooFinanceTickersMetadataScraper,
):
    expected = TickerMetadata(
        ticker="SNT.WA",
        currency_symbol="PLN",
        full_name="Synektik Spólka Akcyjna",
        sector="Healthcare",
        industry="Medical Devices",
        description="Synektik Spólka Akcyjna provides products, services, and IT solutions for surgery, diagnostic imaging, and nuclear medicine applications in Poland. The company sells medical equipment used in diagnostics and therapy, and nuclear medicine. It is also involved in development of IT solutions used in radiology, as well as researches, produces, and sells radiopharmaceutical products used in diagnostics for oncology. In addition, the company operates a research laboratory for diagnostic imaging systems and a service center for medical equipment. Further, it offers maintenance services for medical equipment, as well as acceptance and specialist tests. The company was founded in 2001 and is based in Warsaw, Poland.",
    )

    result = await yf_tickers_metadata_scraper.get_ticker_metadata("SNT.WA")
    assert all(
        getattr(result, attr) == getattr(expected, attr)
        for attr in TickerMetadata.__mapper__.columns.keys()
    )
