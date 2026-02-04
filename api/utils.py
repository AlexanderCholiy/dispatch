from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone


def conversion_utc_datetime(
    value: datetime, show_timezone: bool = True, is_excel_format: bool = False
) -> str:
    """
    Перевод времени из UTC в часовую зону проекта без микросекунд.

    Returns:
        str: Время в локальной зоне проекта в формате ISO или Excel-friendly.
    """
    local_dt = (
        value.astimezone(ZoneInfo(settings.TIME_ZONE)).replace(microsecond=0)
    )

    if is_excel_format:
        fmt = '%Y-%m-%d %H:%M:%S'
        dt_str = local_dt.strftime(fmt)
        if show_timezone:
            # добавляем смещение по Москве
            tz_offset = local_dt.strftime("%z")  # +0300
            tz_formatted = f"{tz_offset[:3]}:{tz_offset[3:]}"  # +03:00
            dt_str += tz_formatted
        return dt_str

    if show_timezone:
        return local_dt.isoformat()

    return local_dt.strftime('%Y-%m-%dT%H:%M:%S')


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
