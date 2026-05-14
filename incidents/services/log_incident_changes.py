from datetime import datetime
from typing import Any, Optional

import pytz
from django.conf import settings
from django.db.models import Model
from django.utils import timezone

from core.constants import DEBUG_MODE
from core.loggers import django_logger
from incidents.models import Incident, IncidentChangeLog
from users.models import User


def serialize_value(val: Any) -> Optional[str]:
    """Преобразует значение в строку для логов."""
    if val is None:
        return None

    if hasattr(val, 'pk'):
        return str(val)

    if isinstance(val, bool):
        return 'Да' if val else 'Нет'

    if isinstance(val, datetime):
        if timezone.is_aware(val):
            target_tz = pytz.timezone(settings.TIME_ZONE)
            dt_converted = val.astimezone(target_tz)
            formatted_time = dt_converted.strftime("%d.%m.%Y %H:%M")
            return f'{formatted_time} (МСК)'

        return val.strftime('%d.%m.%Y %H:%M')

    if isinstance(val, (list, tuple)):
        try:
            return ', '.join(str(item) for item in val)
        except Exception:
            return f'[{", ".join(repr(item) for item in val)}]'

    return str(val)


def get_field_verbose_name(model: Model, field_name: str):
    """
    Возвращает человекочитаемое название поля из verbose_name модели.
    Если не найдено, возвращает само имя поля.
    """
    field = model._meta.get_field(field_name)
    return field.verbose_name if hasattr(field, 'verbose_name') else field_name


def log_incident_changes(
    old_instance: Incident,
    new_instance: Incident,
    changed_by: Optional[User] = None,
    old_categories_names: Optional[set[str]] = None,
):
    """
    Сравнивает old_instance и new_instance, находит изменения
    и сохраняет их в IncidentChangeLog.
    """
    if not old_instance.pk:
        return

    fields_to_track = [
        'pole',
        'base_station',
        'responsible_user',
        'incident_type',
        'incident_subtype',
        'avr_start_date',
        'avr_end_date',
        'rvr_start_date',
        'rvr_end_date',
        'dgu_start_date',
        'dgu_end_date',
        'was_read',
        'auto_close_date',
    ]

    changes_to_create = []

    for field_name in fields_to_track:
        old_val = getattr(old_instance, field_name)
        new_val = getattr(new_instance, field_name)

        pretty_name = get_field_verbose_name(Incident, field_name)

        if old_val != new_val:
            changes_to_create.append(
                IncidentChangeLog(
                    incident=new_instance,
                    changed_by=changed_by,
                    field_name=pretty_name,
                    old_value=serialize_value(old_val),
                    new_value=serialize_value(new_val),
                )
            )

    new_cats_qs = new_instance.categories.all()
    new_cat_names = set(new_cats_qs.values_list('name', flat=True))

    if old_categories_names is not None:
        old_cat_names = old_categories_names
    else:
        old_cat_names = set(
            old_instance.categories.all().values_list('name', flat=True)
        )

    added = new_cat_names - old_cat_names
    removed = old_cat_names - new_cat_names

    if added or removed:
        pretty_name = get_field_verbose_name(Incident, 'categories')

        old_str = ', '.join(sorted(old_cat_names)) if old_cat_names else None
        new_str = ', '.join(sorted(new_cat_names)) if new_cat_names else None

        changes_to_create.append(IncidentChangeLog(
            incident=new_instance,
            changed_by=changed_by,
            field_name=pretty_name,
            old_value=old_str,
            new_value=new_str,
        ))

    if changes_to_create:
        try:
            IncidentChangeLog.objects.bulk_create(
                changes_to_create,
                ignore_conflicts=not DEBUG_MODE
            )
        except Exception as e:
            django_logger.exception(
                f'Ошибка сохранения журнала изменений для {old_instance}: {e}'
            )
