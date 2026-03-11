from typing import TypedDict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from .constants import OLD_NOTIFICATIONS_TTL
from .models import Notification, NotificationLevel


class NotificationData(TypedDict):
    id = int
    title = str
    message = str
    level = str
    read = bool
    data = dict
    created_at = str
    send_at = str


@receiver(post_save, sender=Notification)
def notify_notification_change(sender, instance: Notification, **kwargs):
    now = timezone.now() + timedelta(milliseconds=1)
    week_ago = now - OLD_NOTIFICATIONS_TTL

    if (
        instance.level == NotificationLevel.LOW
        or instance.send_at > now
        or instance.send_at < week_ago
        or instance.read
    ):
        return

    channel_layer = get_channel_layer()
    group_name = f'user_{instance.user.id}'

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'send_notification',
            'data': {
                'id': instance.id,
                'title': instance.title,
                'message': instance.message,
                'level': instance.level,
                'read': instance.read,
                'data': instance.data,
                'created_at': instance.created_at.isoformat(),
                'send_at': instance.send_at.isoformat(),
            },
        },
    )
