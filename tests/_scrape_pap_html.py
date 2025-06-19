# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aiohttp>=3.10.5",
#     "beautifulsoup4>=4.12.3",
# ]
# ///


# uv run tests/_scrape_pap_html.py 2024/07/22 --dest /tmp

import argparse
import asyncio
import itertools
import os
import re
from datetime import UTC, datetime

import aiohttp
from bs4 import BeautifulSoup


def parse_date(v: str) -> datetime:
    try:
        return datetime.strptime(v, "%Y/%m/%d").replace(tzinfo=UTC)
    except Exception as exc:
        msg = "Not a valid datetime, expected YYYY/MM/DD format"
        raise argparse.ArgumentTypeError(msg) from exc


async def visit_and_download(session: aiohttp.ClientSession, path: str, base_url: str, href: str):
    response = await session.get(base_url + href, params={"_x_tr_sl": "en", "_x_tr_tl": "pl", "_x_tr_hl": "en"})
    response.raise_for_status()

    content = await response.text()

    pattern = r"/node/(\d+)\?"
    match_ = re.search(pattern, href)
    # path = os.path.join(path, f"{href.strip("/node/")}.html")
    path = os.path.join(path, f"{match_.group(1)}.html")  # type: ignore
    with open(path, "w", encoding="utf-8") as file:
        print(f"Content saved to {path}")
        file.write(content)


async def find_hrefs(path: str) -> list[str]:
    with open(path, encoding="utf-8") as file:
        soup = BeautifulSoup(file.read(), features="html.parser")
        news = soup.find_all("li", attrs={"class": "news"})
        return [item.select("a")[0]["href"] for item in news]  # type: ignore


async def main():  # noqa: PLR0914
    parser = argparse.ArgumentParser(
        prog="espiebi.pap.pl-scraper",
        description="espiebi.pap.pl scrape html for tests",
    )
    parser.add_argument(
        "date_start",
        type=parse_date,
        help="date for which to scrape html in YYYY/MM/DD format",
    )
    parser.add_argument("--dest")

    args = parser.parse_args()

    page = 0
    date_start = args.date_start
    # date_end = date_start + timedelta(days=1)

    date_start_param = date_start.strftime("%Y-%m-%d")
    # date_end_param = date_end.strftime("%Y-%m-%d")
    date_end_param = date_start_param

    url = "https://espiebi-pap-pl.translate.goog/wyszukiwarka?created={date_start}&enddate={date_end}&page={page}&_x_tr_sl=en&_x_tr_tl=pl&_x_tr_hl=en"
    # url = "https://espiebi.pap.pl/wyszukiwarka?created={date_start}&enddate={date_end}&page={page}"

    async with aiohttp.ClientSession() as session:
        paths = []

        while True:
            target_url = url.format(
                date_start=date_start_param,
                date_end=date_end_param,
                page=page,
            )
            print(f"Looking at {target_url}")

            response = await session.get(target_url)
            response.raise_for_status()
            content = await response.text()

            soup = BeautifulSoup(content, features="html.parser")
            date_str = date_start.strftime("%Y-%m-%d")
            day_h2 = soup.find("h2", string=f"{date_str}")
            if day_h2 is None:
                print(f"h2 with {date_str} not found at {response.url!s}")

            path = os.path.join(args.dest, f"page_{page}.html")
            with open(path, "w", encoding="utf-8") as file:
                file.write(content)
                print(f"Content saved to {path}")
            paths.append(path)

            page += 1

            if day_h2 is None:
                break

        hrefs = await asyncio.gather(*(find_hrefs(path) for path in paths))
        await asyncio.gather(
            *(
                # visit_and_download(session, args.dest, "https://espiebi.pap.pl", href)
                visit_and_download(session, args.dest, "", href)
                for href in itertools.chain.from_iterable(hrefs)
            )
        )


asyncio.run(main())
