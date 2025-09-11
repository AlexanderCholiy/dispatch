from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings


def conversion_utc_datetime(value: datetime) -> str:
    """Перевод времени из UTC в часовую зону проекта без микросекунд"""
    return (
        value
        .astimezone(ZoneInfo(settings.TIME_ZONE))
        .replace(microsecond=0)
        .isoformat()
    )
