import re
from datetime import datetime, timedelta
from typing import Generator

from zoneinfo import ZoneInfo


def date_range(start: datetime, end: datetime) -> Generator[datetime, None, None]:
    return (start + timedelta(days=x) for x in range((end - start).days + 1))


def normalize_raw_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text


def utc_now() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC"))
