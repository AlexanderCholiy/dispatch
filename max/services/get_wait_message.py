from datetime import datetime, timedelta
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

from core.services.formatters import format_timedelta_readable
from max.constants import (
    MAX_INCIDENT_SPAM_KEY_PREFIX,
    MAX_MSG_TTL,
    MaxNotificationData,
    MaxNotificationStatus,
)


def get_wait_message(incident_id: int) -> Optional[str]:
    """
    Проверяет наличие активной задачи и формирует сообщение ожидания.
    Возвращает None, если можно действовать.
    """
    key = f'{MAX_INCIDENT_SPAM_KEY_PREFIX}{incident_id}'
    data: Optional[MaxNotificationData] = cache.get(key)

    if not data:
        return

    status_val = data['status']
    timestamp_str = data['timestamp']

    last_update = datetime.fromisoformat(timestamp_str)
    now = timezone.now()
    delta_seconds = (now - last_update).total_seconds()
    remaining_seconds = MAX_MSG_TTL - delta_seconds

    if remaining_seconds <= 0:
        return

    try:
        status_enum = MaxNotificationStatus(status_val)
    except ValueError:
        status_enum = MaxNotificationStatus.PENDING

    time_str = format_timedelta_readable(timedelta(seconds=remaining_seconds))

    if status_enum == MaxNotificationStatus.PENDING:
        return (
            'Уведомление отправляется. '
            f'Пожалуйста, подождите {time_str}'
        )
    elif status_enum == MaxNotificationStatus.SENT:
        return (
            'Уведомление уже отправлено. '
            f'Повторить можно через {time_str}'
        )
    elif status_enum == MaxNotificationStatus.ERROR:
        return (
            'Не удалось отправить уведомление. '
            f'Повторить можно через {time_str}'
        )


def save_notification_status(
    incident_id: int,
    status: MaxNotificationStatus,
):
    """Сохраняет статус и время в Redis в формате JSON."""
    key = f'{MAX_INCIDENT_SPAM_KEY_PREFIX}{incident_id}'

    payload: MaxNotificationData = {
        'timestamp': timezone.now().isoformat(),
        'status': status.value,
    }

    cache.set(key, payload, timeout=MAX_MSG_TTL)
