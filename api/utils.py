from datetime import datetime, timedelta
from pathlib import Path
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


def is_file_fresh(
    file_path: Path, ttl: timedelta
) -> tuple[bool, datetime | None]:
    """
    Проверяет, актуален ли файл по TTL.
    Возвращает (is_fresh, modified_time)
    """
    if not file_path.exists():
        return False, None

    modified_time = datetime.fromtimestamp(
        file_path.stat().st_mtime,
        tz=timezone.get_current_timezone()
    )
    is_fresh = timezone.now() - modified_time < ttl
    return is_fresh, modified_time
