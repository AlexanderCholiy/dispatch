from celery import shared_task
from django.core.cache import cache

from core.loggers import celery_logger, max_api_logger
from incidents.models import Incident, IncidentHistory
from max.constants import (
    MAX_CHAT_ID,
    MAX_INCIDENT_SPAM_KEY_PREFIX,
    MaxNotificationData,
    MaxNotificationStatus,
)
from max.max_api import max_api
from max.services.get_wait_message import save_notification_status


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    queue='low',
    soft_time_limit=30,
    time_limit=40,
    acks_late=True,
)
def send_max_incident_notification(
    self,
    incident_id: int,
    sender_user_id: int,
    text: str,
):
    """Задача для отправки уведомлений в MAX."""
    key = f'{MAX_INCIDENT_SPAM_KEY_PREFIX}{incident_id}'
    cached_data: None | MaxNotificationData = cache.get(key)

    if cached_data:
        current_status = cached_data['status']

        if current_status == MaxNotificationStatus.SENT.value:
            celery_logger.warning(
                f'Пропуск отправки для инцидента {incident_id}. '
                f'Текущий статус: {current_status}.'
            )
            return

    try:
        incident = Incident.objects.get(id=incident_id)
    except Incident.DoesNotExist:
        celery_logger.warning(
            f'Инцидент с ID {incident_id} не найден. Пропускаем отправку.'
        )
        return

    try:
        max_api.send_message(text, chat_id=MAX_CHAT_ID)
        save_notification_status(
            incident_id,
            MaxNotificationStatus.SENT,
        )

        try:
            IncidentHistory.objects.create(
                incident=incident,
                action='Отправлено уведомление в MAX',
                performed_by_id=sender_user_id,
            )
        except Exception as history_error:
            celery_logger.exception(
                'Не удалось записать запись в IncidentHistory для '
                f'инцидента {incident_id}: {history_error}'
            )

    except Exception as e:
        max_api_logger.exception(
            f'Ошибка при отправки уведомления в MAX: {e}'
        )

        save_notification_status(
            incident_id,
            MaxNotificationStatus.ERROR,
        )

        raise self.retry(exc=e, countdown=60)
