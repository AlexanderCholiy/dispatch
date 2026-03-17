import json
from datetime import timedelta
from typing import Optional, TypedDict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.urls import reverse
from django.utils import timezone

from .constants import (
    MAX_NOTIFICATION_PREWIE_LEN,
    NOTIFICATIONS_PER_PAGE,
    OLD_NOTIFICATIONS_TTL,
)
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


class NotificationsConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope['user']
        if user.is_anonymous:
            await self.close()
            return

        self.user = user
        self.group_name = f'user_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        unread = await self.get_unread_notifications()
        count = await self.get_unread_count()
        await self.send_json(
            {'type': 'init', 'notifications': unread, 'count': count}
        )

    async def disconnect(self, close_code: int):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    @database_sync_to_async
    def get_unread_notifications(self) -> list[NotificationData]:
        now = timezone.now() + timedelta(milliseconds=1)
        ago = now - OLD_NOTIFICATIONS_TTL

        qs = (
            Notification.objects
            .filter(
                user=self.user,
                read=False,
                level__in=[NotificationLevel.MEDIUM, NotificationLevel.HIGH],
                send_at__lte=now,
                send_at__gte=ago,
            )
            .order_by('send_at', 'created_at', 'id')
            [:NOTIFICATIONS_PER_PAGE]
        )

        notifications = []

        for n in qs:
            notification_url = reverse(
                'notifications:notification_detail', args=[n.id]
            )
            incident_url = None

            if isinstance(n.data, dict):
                incident_id = n.data.get('incident_id')
                if isinstance(incident_id, int) and incident_id > 0:
                    incident_url = reverse(
                        'incidents:incident_detail', args=[incident_id]
                    )

            message = n.message or ''

            if len(message) > MAX_NOTIFICATION_PREWIE_LEN:
                message = message[:MAX_NOTIFICATION_PREWIE_LEN] + '…'

            notifications.append({
                'id': n.id,
                'title': n.title,
                'message': message,
                'level': n.level,
                'notification_url': notification_url,
                'incident_url': incident_url,
                'send_at': n.send_at.isoformat(),
            })

        return notifications

    @database_sync_to_async
    def get_unread_count(self) -> int:
        now = timezone.now() + timedelta(seconds=10)
        # ago = now - OLD_NOTIFICATIONS_TTL

        return Notification.objects.filter(
            user=self.user,
            read=False,
            level__in=[NotificationLevel.MEDIUM, NotificationLevel.HIGH],
            send_at__lte=now,
            # send_at__gte=ago,
        ).count()

    @database_sync_to_async
    def mark_read(self, notif_id: Optional[int] = None):
        qs = Notification.objects.filter(user=self.user, read=False)

        if notif_id and isinstance(notif_id, int):
            qs = qs.filter(id=notif_id)
        qs.update(read=True)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        notif_id = data.get('id')

        if action == 'mark_read' and notif_id:
            await self.mark_read(notif_id)
        elif action == 'mark_all':
            await self.mark_read()

        unread = await self.get_unread_notifications()
        count = await self.get_unread_count()
        await self.send_json(
            {'type': 'update', 'notifications': unread, 'count': count}
        )

    async def send_notification(self, event):
        notif: Optional[NotificationData] = event.get('data')

        if (
            not notif or notif.get('level', 'low') == NotificationLevel.LOW
        ):
            return

        send_at = notif.get('send_at')
        if send_at:
            send_time = timezone.datetime.fromisoformat(send_at)
            now = timezone.now()

            if send_time < now - OLD_NOTIFICATIONS_TTL:
                return

        count = await self.get_unread_count()

        notif_id = notif['id']

        notification_url = reverse(
            'notifications:notification_detail', args=[notif.get('id')]
        ) if notif_id else None

        incident_url = None
        notif_data = notif['data']

        if isinstance(notif_data, dict):
            incident_id = notif_data.get('incident_id')
            if isinstance(incident_id, int) and incident_id > 0:
                incident_url = reverse(
                    'incidents:incident_detail', args=[incident_id]
                )

        message = notif.get('message') or ''

        if len(message) > MAX_NOTIFICATION_PREWIE_LEN:
            message = message[:MAX_NOTIFICATION_PREWIE_LEN] + '…'

        notification = {
            'id': notif['id'],
            'title': notif['title'],
            'message': message,
            'level': notif['level'],
            'notification_url': notification_url,
            'incident_url': incident_url,
            'send_at': notif['send_at'],
        }

        await self.send_json(
            {
                'type': 'notification',
                'notification': notification,
                'count': count
            }
        )
