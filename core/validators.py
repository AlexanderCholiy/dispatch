from typing import Optional
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime


def get_aware_datetime(raw_date_str: Optional[str]) -> Optional[datetime]:
    """Парсит строку из datetime-local и приводит к часовому поясу проекта."""

    if not raw_date_str or not isinstance(raw_date_str, str):
        return None

    try:
        dt = parse_datetime(raw_date_str.strip())

        if dt:
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt

    except (ValueError, TypeError):
        return None

    return None
