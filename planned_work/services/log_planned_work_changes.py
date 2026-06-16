from typing import Optional

from django.utils import timezone

from core.constants import MAX_LG_DESCRIPTION
from core.loggers import django_logger
from core.services.formatters import truncate_text
from emails.models import EmailMessage
from incidents.services.log_incident_changes import (
    get_field_verbose_name,
    serialize_value,
)
from planned_work.models import (
    PlannedWork,
    PlannedWorkChangeLog,
    PlannedWorkReason,
)
from users.models import User


def log_planned_work_changes(
    old_instance: Optional[PlannedWork],
    new_instance: PlannedWork,
    changed_by: Optional[User] = None,
    old_email_ids: Optional[list[int]] = None,
):
    """
    Сравнивает old_instance и new_instance, находит изменения полей
    и сохраняет их в PlannedWorkChangeLog.
    Также обрабатывает изменения в ManyToMany (emails).
    """
    if not new_instance.pk:
        return

    fields_to_track = [
        'pole',
        'reason',
        'start_date',
        'end_date',
        'author',
    ]

    changes_to_create = []
    now = timezone.now()

    # 1. Логирование изменений полей:
    if old_instance:
        for field_name in fields_to_track:
            old_val = getattr(old_instance, field_name)
            new_val = getattr(new_instance, field_name)

            if field_name == 'reason':
                try:
                    old_val = PlannedWorkReason(old_val).label
                except ValueError:
                    pass

                try:
                    new_val = PlannedWorkReason(new_val).label
                except ValueError:
                    pass

            if old_val == new_val:
                continue

            pretty_name = get_field_verbose_name(PlannedWork, field_name)

            changes_to_create.append(
                PlannedWorkChangeLog(
                    planned_work=new_instance,
                    changed_by=changed_by,
                    field_name=pretty_name,
                    old_value=serialize_value(old_val),
                    new_value=serialize_value(new_val),
                    created_at=now,
                )
            )

    # 2. Логирование изменений в связях ManyToMany (emails):
    if old_email_ids is not None:
        current_emails_list = list(new_instance.emails.all())
        current_ids = set(e.id for e in current_emails_list)
        old_ids_set = set(old_email_ids)

        added_ids = current_ids - old_ids_set
        removed_ids = old_ids_set - current_ids

        # Загружаем данные для удаленных писем одним запросом:
        removed_objs_map = {}
        if removed_ids:
            removed_qs = (
                EmailMessage.objects
                .filter(id__in=list(removed_ids))
                .only('id', 'email_subject')
            )
            removed_objs_map = {obj.id: obj for obj in removed_qs}

        for email_obj in current_emails_list:
            if email_obj.id in added_ids:
                subject = email_obj.email_subject or "Без темы"
                safe_subject = truncate_text(subject, MAX_LG_DESCRIPTION)

                field_name = f'Связь с письмом ID: {email_obj.id}'

                changes_to_create.append(
                    PlannedWorkChangeLog(
                        planned_work=new_instance,
                        changed_by=changed_by,
                        field_name=field_name,
                        old_value=None,
                        new_value=safe_subject,
                        created_at=now,
                    )
                )

        for rid in removed_ids:
            # Получаем тему письма, если оно еще есть в БД
            if rid in removed_objs_map:
                obj = removed_objs_map[rid]
                subject = obj.email_subject or "Без темы"
                safe_subject = truncate_text(subject, MAX_LG_DESCRIPTION)
            else:
                safe_subject = f'Удаленное письмо ID: {rid}'

            field_name = f"Связь с письмом ID: {rid}"

            changes_to_create.append(
                PlannedWorkChangeLog(
                    planned_work=new_instance,
                    changed_by=changed_by,
                    field_name=field_name,
                    old_value=safe_subject,
                    new_value=None,
                    created_at=now,
                )
            )

    if changes_to_create:
        try:
            PlannedWorkChangeLog.objects.bulk_create(
                changes_to_create,
                ignore_conflicts=True,
            )
        except Exception as e:
            django_logger.exception(
                f'Ошибка сохранения журнала изменений для ПЛР {new_instance}: '
                f'{e}'
            )
