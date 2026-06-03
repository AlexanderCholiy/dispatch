from datetime import datetime
from typing import Optional

from django.utils import timezone
from django.utils.dateparse import parse_datetime


def get_aware_datetime(
    raw_date_str: Optional[str],
    force_min_seconds: bool = True
) -> Optional[datetime]:
    """
    Парсит строку из datetime-local и приводит к часовому поясу проекта.

    Args:
        raw_date_str: Строка даты (например, '2023-10-01T12:30' или
        '2023-10-01T12:30:45').
        force_min_seconds:
            - Если True и секунд нет в строке -> устанавливает 00 секунд (
            начало минуты).
            - Если False и секунд нет в строке -> устанавливает 59.999999
            секунд (конец минуты).
    """
    if not raw_date_str or not isinstance(raw_date_str, str):
        return None

    raw_date_str = raw_date_str.strip()

    try:
        has_seconds = len(raw_date_str.split(':')) > 2

        dt = parse_datetime(raw_date_str)

        if dt:
            if not has_seconds:
                if force_min_seconds:
                    dt = dt.replace(second=0, microsecond=0)
                else:
                    dt = dt.replace(second=59, microsecond=999999)

            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt

    except (ValueError, TypeError):
        return None

    return None
