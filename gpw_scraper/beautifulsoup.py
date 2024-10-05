from bs4 import BeautifulSoup as BeautifulSoupBase
from bs4 import NavigableString, Tag
from loguru import logger


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
