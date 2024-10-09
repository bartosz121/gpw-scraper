import asyncio
import itertools
import re
from datetime import datetime, timedelta
from typing import (
    Literal,
    NamedTuple,
    Sequence,
    cast,
)

import aiohttp
from bs4 import Tag
from loguru import logger

from gpw_scraper import llm, utils
from gpw_scraper.beautifulsoup import BeautifulSoup
from gpw_scraper.models.espi_ebi import EspiEbi


class EspiEbiScrapedInfo(NamedTuple):
    type: Literal["ESPI", "EBI"]
    title: str
    description: str | None
    company: str
    url: str
    llm: str | None = None


class PapHrefItem(NamedTuple):
    href: str
    date: datetime


class EspiEbiPapScraper:
    url = "https://espiebi-pap-pl.translate.goog"
    db_source_base_url = "https://espiebi.pap.pl"
    node_pattern = r"(/node/\d+)\?"
    google_translate_params = {"_x_tr_sl": "en", "_x_tr_tl": "pl", "_x_tr_hl": "en"}

    async def scrape_hrefs(
        self,
        pap_session: aiohttp.ClientSession,
        date: datetime,
        ignore_list: Sequence[str] = [],
    ) -> list[PapHrefItem]:
        created_param = date.strftime("%Y-%m-%d")
        end_date_param = created_param
        pap_being_stupid = False
        pap_being_stupid_2 = False
        page = 0

        hrefs: list[PapHrefItem] = []
        while True:
            logger.info(f"Scraping items at {page=}")
            response = await pap_session.get(
                "/wyszukiwarka",
                params={
                    "created": created_param,
                    "enddate": end_date_param,
                    "page": page,
                    **EspiEbiPapScraper.google_translate_params,
                },
            )
            response.raise_for_status()
            content = await response.text()
            logger.debug("Parsing html")
            soup = BeautifulSoup(content, features="html.parser")

            date_str = date.strftime("%Y-%m-%d")
            logger.debug("Looking for h2 tag with target date")
            day_h2 = soup.find("h2", string=date_str)
            if day_h2 is None:
                logger.info(f"h2 with {date_str} not found at {response.url!s}")
                if pap_being_stupid is False:
                    logger.info(
                        "Trying +1 day in created and end url param, maybe pap espi ebi page is stupid?"
                    )
                    pap_being_stupid = True
                    created_param = (date + timedelta(days=1)).strftime("%Y-%m-%d")
                    end_date_param = created_param
                    continue
                if pap_being_stupid_2 is False:
                    logger.info(
                        "Trying real date in created and +1 day in end, maybe pap espi ebi page is stupid? (squared)"
                    )
                    pap_being_stupid_2 = True
                    created_param = date.strftime("%Y-%m-%d")
                    end_date_param = (date + timedelta(days=1)).strftime("%Y-%m-%d")
                    continue
                break

            logger.debug("Looking for ul with items")
            news_ul = day_h2.find_next("ul")
            if news_ul is None:
                logger.info(f"ul with news not found at {response.url!s}")
                break

            logger.debug("Looking for li;s within ul")
            li_elements = cast(Tag, news_ul).find_all("li")
            if len(li_elements) == 0:
                logger.error(f"li elements not found at {response.url!s}")
                break

            for item in li_elements:
                logger.debug(f"Parsing item {item!s}")
                hour = item.select_one(".hour").text
                a_tag = item.select("a")[0] if len(item.select("a")) > 0 else None
                if hour is None or a_tag is None:
                    logger.error(f"Required data not found for {item!s}")
                    continue

                hour_str = hour.strip()
                href_absolute = a_tag["href"]  # absolute because of google translate
                m = re.search(EspiEbiPapScraper.node_pattern, href_absolute)
                if m is None:
                    logger.error(f"Regex failed on {href_absolute}")
                    continue

                href = m.group(1)

                if href in ignore_list:
                    logger.info(f"item in ignore list {item!s}")
                    continue

                item_hh, item_mm = map(int, hour_str.split(":"))
                item_date = date.replace(hour=item_hh, minute=item_mm)

                hrefs.append(PapHrefItem(date=item_date, href=href))

            page += 1

        return hrefs

    async def scrape_hrefs_in_range(
        self,
        pap_session: aiohttp.ClientSession,
        date_start: datetime,
        date_end: datetime,
        ignore_list: Sequence[str] = [],
    ) -> list[PapHrefItem]:
        href_tasks = [
            self.scrape_hrefs(pap_session, date, ignore_list)
            for date in utils.date_range(date_start, date_end)
        ]

        return list(itertools.chain.from_iterable(await asyncio.gather(*href_tasks)))

    async def scrape_item_data(
        self,
        pap_session: aiohttp.ClientSession,
        href_item: PapHrefItem,
        clients: Sequence[llm.LLMClientManaged],
    ) -> EspiEbi:
        logger.info(f"{href_item} Scraping item")
        response = await pap_session.get(
            href_item.href, params=EspiEbiPapScraper.google_translate_params
        )
        response.raise_for_status()

        content = await response.text()
        logger.debug(f"{href_item.href} Parsing item html")
        soup = BeautifulSoup(content, features="html.parser")

        logger.debug(f"{href_item.href} Looking for item type")
        source_sibling_div = soup.find(
            "div", text=re.compile(r"Źródło (raportu|danych)")
        )
        if source_sibling_div is None:
            msg = f"Source sibling div not found in {href_item.href}"
            logger.warning(msg)
            raise ValueError(msg)

        source_div = source_sibling_div.find_next("div")
        if source_div is None:
            msg = f"Source div not found in {href_item.href}"
            logger.error(msg)
            raise ValueError(msg)

        source = source_div.text.strip()
        if source not in {"ESPI", "EBI"}:
            msg = f"Unexpected source: {source!r} in {href_item.href}"
            logger.error(msg)
            raise ValueError(msg)

        if source == "ESPI":
            parsed = await self._parse_espi(
                href_item.href,
                soup,
                clients,
            )
        else:
            parsed = await self._parse_ebi(href_item.href, soup)

        item = EspiEbi(
            type=parsed.type,
            title=parsed.title,
            description=parsed.description,
            company=parsed.company,
            source=EspiEbiPapScraper.db_source_base_url + parsed.url,
            parsed_by_llm=parsed.llm,
            date=href_item.date,
        )
        return item

    async def _parse_espi(
        self, url: str, soup: BeautifulSoup, clients: Sequence[llm.LLMClientManaged]
    ) -> EspiEbiScrapedInfo:
        logger.info(f"{url} Parsing ESPI item")
        logger.debug(f"{url} Looking for item title in html")

        item_title_from_header = soup.pap_get_item_title_from_h1()
        logger.debug(f"{item_title_from_header=}")

        item_title_from_content = soup.pap_get_text_from_tr(
            (soup.find("td", string="Tytuł"))
        )
        if item_title_from_content is not None:
            item_title_from_content = item_title_from_content.lstrip(
                "Tytuł:"
            ).strip()  # FIXME: yikes
        logger.debug(f"{item_title_from_content=}")

        logger.debug(f"{url} Looking for espi content")
        item_content = soup.pap_espi_get_content()
        logger.debug(f"{item_content=}")

        logger.debug(f"{url} Looking for company name")
        company_name = soup.pap_get_text_from_tr(
            (soup.find("td", string="Nazwa emitenta"))
        )
        if company_name is None:
            msg = f"{url} Company name not found in {url}"
            logger.error(msg)
            raise ValueError(msg)

        page_content = soup.find("div", {"id": "main", "class": "container"})
        if page_content is None:
            msg = f"{url} Page content div not found"
            logger.error(msg)
            raise ValueError(msg)

        item_title = item_title_from_header or item_title_from_content
        item_description = item_content
        llm_model = None

        if item_title is None or item_description is None:
            logger.debug(f"{url} Asking LLM for ESPI title and description")
            for client in clients:
                result = await client.get_espi_summary_until_valid(page_content.text)
                if result is not None:
                    item_title = item_title or result[0].title
                    item_description = item_description or result[0].description
                    llm_model = result[1]
                    break

        if item_title is None:
            raise ValueError(f"{url} item title is None")

        item_title = utils.normalize_raw_text(item_title)
        if item_description:
            item_description = utils.normalize_raw_text(item_description)

        return EspiEbiScrapedInfo(
            type="ESPI",
            title=item_title,
            description=item_description,
            company=company_name,
            url=url,
            llm=llm_model,
        )

    async def _parse_ebi(self, url: str, soup: BeautifulSoup) -> EspiEbiScrapedInfo:
        logger.info(f"{url} Parsing EBI item")

        logger.debug(f"{url} Looking for company name")
        company_name_text = soup.pap_get_text_after_semicolon(
            soup.find("strong", string="Firma:")
        )
        if company_name_text is None:
            msg = f"Company text not found in {url}"
            logger.error(msg)
            raise ValueError(msg)

        logger.debug(f"{url} Looking for item title in html")
        item_title = soup.pap_get_text_after_semicolon(
            soup.find("strong", string="Tytuł:")
        )
        if item_title is None:
            msg = f"Item title not found in {url}"
            logger.error(msg)
            raise ValueError(msg)
        item_title = item_title.lstrip("Tytuł:").strip()

        logger.debug(f"{url} Looking for item content in html")
        item_content_div = soup.find("div", attrs={"class": "report-content"})
        if item_content_div is None:
            msg = f"Item content div not found in {url}"
            logger.error(msg)
            raise ValueError(msg)

        item_title = utils.normalize_raw_text(item_title)
        item_content = utils.normalize_raw_text(item_content_div.text)

        return EspiEbiScrapedInfo(
            type="EBI",
            title=item_title,
            description=item_content,
            company=company_name_text,
            url=url,
        )

    async def scrape(
        self,
        pap_session: aiohttp.ClientSession,
        date_start: datetime,
        date_end: datetime,
        ignore_list: Sequence[str],
        clients: Sequence[llm.LLMClientManaged],
    ) -> list[EspiEbi]:
        logger.info("Scraping")

        href_tasks = [
            self.scrape_hrefs(pap_session, date, ignore_list)
            for date in utils.date_range(date_start, date_end)
        ]

        hrefs = itertools.chain.from_iterable(await asyncio.gather(*href_tasks))

        item_tasks = [
            self.scrape_item_data(pap_session, href, clients) for href in hrefs
        ]

        items = await asyncio.gather(*item_tasks)
        logger.debug(f"{items=!r}")
        return items
