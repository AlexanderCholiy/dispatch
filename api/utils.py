from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone


def conversion_utc_datetime(value: datetime) -> str:
    """Перевод времени из UTC в часовую зону проекта без микросекунд"""
    return (
        value
        .astimezone(ZoneInfo(settings.TIME_ZONE))
        .replace(microsecond=0)
        .isoformat()
    )


def get_first_day_prev_month() -> datetime:
    now = timezone.localtime(timezone.now())
    return (
        now.replace(day=1) - relativedelta(months=1)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
