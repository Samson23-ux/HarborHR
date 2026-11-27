from datetime import datetime


def parse_iso_datetime(iso_datetime: str) -> datetime | None:
    try:
        return datetime.fromisoformat(iso_datetime)
    except ValueError, TypeError:
        return None
