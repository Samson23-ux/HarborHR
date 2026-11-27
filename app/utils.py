from datetime import datetime


def is_valid_datetime(iso_datetime: str) -> datetime | bool:
    try:
        return datetime.fromisoformat(iso_datetime)
    except ValueError, TypeError:
        return False
