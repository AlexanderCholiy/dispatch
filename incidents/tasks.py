from typing import Optional

from celery import shared_task
from django.db.models import Prefetch
from django.utils import timezone

from core.constants import DATETIME_FORMAT
from core.loggers import celery_logger
from notifications.models import Notification, NotificationLevel

from .constants import (
    AVR_CATEGORY,
    DGU_CATEGORY,
    END_STATUS_NAME,
    NOTIFIED_OP_END_STATUS_NAME,
    RVR_CATEGORY,
)
from .models import Incident, IncidentStatus, IncidentStatusHistory


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    queue='low',
    soft_time_limit=30,
    time_limit=40,
    acks_late=True,
)
def close_incident_auto(self, incident_id: int):
    """Задача для автоматического закрытия инцидента."""
    try:
        status_history_qs = (
            IncidentStatusHistory.objects
            .select_related('status', 'status__status_type')
            .order_by('-insert_date', '-id')
        )

        incident = (
            Incident.objects
            .select_related('responsible_user')
            .prefetch_related(
                'categories',
                Prefetch(
                    'status_history',
                    queryset=status_history_qs,
                    to_attr='prefetched_status_history'
                ),
            )
            .get(pk=incident_id)
        )

        last_status: Optional[IncidentStatus] = (
            incident.prefetched_status_history[0].status
            if incident.prefetched_status_history
            else None
        )

        if not incident.auto_close_date:
            celery_logger.debug(
                f'Инцидент {incident} не имеет даты автозакрытия. Пропуск.'
            )
            return

        if not last_status or last_status.name != NOTIFIED_OP_END_STATUS_NAME:
            celery_logger.debug(
                f'Статус инцидента {incident}: {last_status}. Пропуск.'
            )
            return

        now = timezone.now()

        if now < incident.auto_close_date or incident.is_incident_finish:
            return

        closed_status, _ = IncidentStatus.objects.get_or_create(
            name=END_STATUS_NAME
        )

        close_time = timezone.localtime(incident.auto_close_date)
        formatted_time = close_time.strftime(DATETIME_FORMAT)

        comments = (
            f'Автоматическое закрытие по таймеру ({formatted_time})'
        )

        incident.is_incident_finish = True
        incident.statuses.add(closed_status)

        category_names = {
            c.name for c in incident.categories.all()
        }

        IncidentStatusHistory.objects.create(
            incident=incident,
            status=closed_status,
            comments=comments,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )

        incident.auto_close_date = None
        incident.save()

        if incident.responsible_user:
            Notification.objects.create(
                user=incident.responsible_user,
                title=f'Автозакрытие инцидента: {incident}',
                message=comments,
                level=NotificationLevel.MEDIUM,
                data={'incident_id': incident.id},
            )

        celery_logger.debug(f'Инцидент {incident}: {comments}')

    except Incident.DoesNotExist:
        celery_logger.error(f'Инцидент ID: {incident_id} не найден.')
    except Exception as e:
        celery_logger.exception(
            f'Ошибка при автозакрытии инцидента {incident_id}: {e}'
        )
        raise self.retry(exc=e, countdown=60)


@shared_task
def check_stale_auto_closes():
    """
    Периодическая задача.
    Проверяет инциденты с установленной auto_close_date, которые должны были
    закрыться, но не закрылись.
    """
    now = timezone.now()

    stale_incidents = Incident.objects.filter(
        auto_close_date__lte=now,
        is_incident_finish=False,
    ).exclude(auto_close_date=None)

    count = 0
    for incident in stale_incidents:
        celery_logger.warning(
            f'Найден зависший инцидент {incident} с просроченной датой '
            'автозакрытия. Принудительное закрытие.'
        )

        close_incident_auto.delay(incident.id)
        count += 1

    if count > 0:
        celery_logger.info(
            f'Обработано {count} зависших инцидентов с автозакрытием.'
        )
    else:
        celery_logger.debug('Зависших инцидентов с автозакрытием не найдено.')
