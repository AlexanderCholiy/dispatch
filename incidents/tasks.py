from celery import shared_task
from django.utils import timezone
from .models import Incident, IncidentStatus, IncidentStatusHistory
from .constants import (
    END_STATUS_NAME,
    AVR_CATEGORY,
    RVR_CATEGORY,
    DGU_CATEGORY,
)
from core.loggers import celery_logger
from notifications.models import Notification, NotificationLevel
from core.constants import DATETIME_FORMAT


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
        incident = Incident.objects.get(pk=incident_id)

        if not incident.auto_close_date:
            celery_logger.debug(
                f'Инцидент {incident} не имеет даты автозакрытия. Пропуск.'
            )
            return

        now = timezone.now()

        if now < incident.auto_close_date or incident.is_incident_finish:
            return

        closed_status, _ = IncidentStatus.objects.get_or_create(
            name=END_STATUS_NAME
        )

        comments = (
            'Автоматическое закрытие по таймеру '
            f'({incident.auto_close_date.strftime(DATETIME_FORMAT)})'
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
