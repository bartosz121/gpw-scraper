import re

from bs4 import BeautifulSoup as BeautifulSoupBase
from bs4 import NavigableString, Tag
from loguru import logger

from gpw_scraper import utils


class BeautifulSoup(BeautifulSoupBase):
    def pap_get_text_after_semicolon(
        self, tag: Tag | NavigableString | None
    ) -> str | None:
        if tag is None:
            return None

        tag_parent = tag.parent
        if tag_parent is None:
            return None

        return tag_parent.text.strip("Firma:").strip()

    def pap_get_text_from_tr(self, tag: Tag | NavigableString | None) -> str | None:
        logger.debug(tag)
        if tag is None:
            return None

        tag_parent = tag.parent
        logger.debug(tag_parent)
        if tag_parent is None:
            return None

        tds = tag_parent.find_all("td")
        logger.debug(tds)
        if len(tds) < 2:
            return None

        target_text = tds[1].text.strip()

        logger.debug(f"returning {target_text}")
        return target_text

    def pap_get_item_title_from_h1(self) -> str | None:
        el = self.select_one("div#page-wrapper div#page h1.mainTitle")
        if el is None:
            return None
        text = el.text.replace("\n", " ").strip()
        return text

    def pap_espi_get_content(self) -> str | None:
        def string_pl(tag):
            return tag.name == "tr" and tag.find(string="Treść raportu:") is not None

        def string_en(tag):
            return (
                tag.name == "tr"
                and tag.find(string="Contents of the report:") is not None
            )

        tr_with_heading = self.find(string_pl)
        if tr_with_heading is None:
            tr_with_heading = self.find(string_en)
            if tr_with_heading is None:
                return None

        next_tr_with_content = tr_with_heading.find_next_sibling("tr")
        if next_tr_with_content is None:
            return None

        return next_tr_with_content.text.strip() or None

    def yf_historical_data_get_currency(self) -> str | None:
        tag = self.find(class_="currency")
        if tag is None:
            return None
        text = tag.get_text(strip=True)

        m = re.search(utils.ISO_4217, text)
        return None if m is None else m.group()

    def yf_profile_get_company_name(self) -> str | None:
        profile_header = self.find(attrs={"data-testid": "quote-hdr"})
        if profile_header is None:
            return None

        h1 = profile_header.find("h1")
        if h1 is None or isinstance(h1, int):
            return None

        name_with_ticker_at_the_end = h1.get_text(strip=True)
        name = re.sub(r"\s\(.*\)$", "", name_with_ticker_at_the_end)
        return name

    def yf_profile_get_description(self, cleanup: bool = False) -> str | None:
        description_el = self.find(attrs={"data-testid": "description"})
        if description_el is None:
            return None

        p = description_el.find("p")
        if p is None or isinstance(p, int):
            return None

        content = p.get_text(strip=True)
        if cleanup:
            content = utils.normalize_raw_text(content)

        return content

    def yf_profile_get_currency(self) -> str | None:
        exchange_el = self.find(class_="exchange")
        if exchange_el is None:
            return None
        content = exchange_el.get_text(strip=True)

        m = re.search(utils.ISO_4217, content)
        return m.group() if m else None

    def yf_profile_get_sector(self) -> str | None:
        company_stats = self.find(class_="company-stats")
        if company_stats is None:
            return None
        content = company_stats.get_text()

        m = re.search(r"Sector:\s*(.*?)\s*Industry", content)
        return m.group(1) if m else None

    def yf_profile_get_industry(self) -> str | None:
        company_stats = self.find(class_="company-stats")
        if company_stats is None:
            return None
        content = company_stats.get_text()

        m = re.search(r"Industry:\s*(.*?)\s*Full Time Employees", content)
        return m.group(1) if m else None
