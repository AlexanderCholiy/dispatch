from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

from .constants import OLD_NOTIFICATIONS_TTL
from .models import Notification, NotificationLevel
from core.loggers import celery_logger


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue='medium',
    soft_time_limit=5,
    time_limit=10,
    acks_late=True,
)
def send_notification_task(self, notification_id: int):
    try:
        notification = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        celery_logger.warning(f'Уведомление {notification_id} отсутствует')
        return

    now = timezone.now()
    week_ago = now - OLD_NOTIFICATIONS_TTL

    if (
        notification.level == NotificationLevel.LOW
        or notification.send_at < week_ago
        or notification.read
    ):
        if not notification.scheduled:
            Notification.objects.filter(
                pk=notification.pk, scheduled=False
            ).update(scheduled=True)
        celery_logger.warning(
            (
                f'Уведомление {notification_id} игнорируется (low / старое / '
                'прочитано)'
            )
        )
        return

    channel_layer = get_channel_layer()
    group_name = f'user_{notification.user.id}'

    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'send_notification',
                'data': {
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'level': notification.level,
                    'read': notification.read,
                    'data': notification.data,
                    'created_at': notification.created_at.isoformat(),
                    'send_at': notification.send_at.isoformat(),
                },
            },
        )
        Notification.objects.filter(pk=notification.pk).update(scheduled=True)
    except Exception as e:
        celery_logger.error(
            f'Ошибка отправки уведомления {notification.id}: {e}'
        )
        Notification.objects.filter(pk=notification.pk).update(scheduled=False)
        raise self.retry(exc=e)


@shared_task
def check_overdue_notifications():
    """Проверка уведомлений, которые должны быть отправлены, но не были."""
    now = timezone.now() + timedelta(seconds=1)
    ago = now - OLD_NOTIFICATIONS_TTL

    notifications = Notification.objects.filter(
        read=False,
        scheduled=False,
        send_at__lte=now,
        send_at__gte=ago,
    ).exclude(level=NotificationLevel.LOW)
    total = notifications.count()
    sent_count = 0

    for notification in notifications:
        send_notification_task.delay(notification.id)
        sent_count += 1

    if total:
        celery_logger.warning(
            (
                f'Проверка просроченных уведомлений: {sent_count} / {total} '
                'уведомлений отправлены в очередь'
            )
        )
