from datetime import date
from typing import Optional

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date


def validate_date_range(
    start_date: Optional[str], end_date: Optional[str]
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

    return start, end


def validate_responsible_user(responsible_user: Optional[int | str]):
    if responsible_user is not None and responsible_user != 'none':
        try:
            responsible_user = int(responsible_user)
        except (TypeError, ValueError):
            raise ValidationError({
                'responsible_user': 'Должен быть числом'
            })


def validate_operator_group(operator_group: Optional[str]):
    if operator_group is not None:
        operator_group = operator_group.strip()
        if not operator_group:
            raise ValidationError({
                'operator_group': 'Не может быть пустой строкой'
            })


def validate_incident_duration_min(incident_duration_min: Optional[int]):
    if incident_duration_min is not None:
        try:
            incident_duration_min = int(incident_duration_min)
            if incident_duration_min < 1:
                raise ValidationError(
                    {'incident_duration_min': 'TTL должен быть > 0'}
                )
        except Exception:
            raise ValidationError({
                'incident_duration_min': 'Не верный формат TTL'
            })
