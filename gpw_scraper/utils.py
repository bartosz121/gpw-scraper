from datetime import datetime, timedelta
from typing import Generator


def date_range(start: datetime, end: datetime) -> Generator[datetime, None, None]:
    return (start + timedelta(days=x) for x in range((end - start).days + 1))
