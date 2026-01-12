from datetime import date
from typing import Optional

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date


def validate_date_range(
    start_date: str | None, end_date: str | None
) -> tuple[Optional[date], Optional[date]]:
    """Универсальный валидатор дат."""

    start = parse_date(start_date) if start_date else None
    end = parse_date(end_date) if end_date else None

    if start_date and not start:
        raise ValidationError(
            'Некорректный формат start_date. Используй YYYY-MM-DD'
        )

    if end_date and not end:
        raise ValidationError(
            'Некорректный формат end_date. Используй YYYY-MM-DD'
        )

    if start and end and start > end:
        raise ValidationError('start_date не может быть больше end_date')

    today = timezone.now().date()
    if end and end > today:
        raise ValidationError('end_date не может быть в будущем')

    return start, end
