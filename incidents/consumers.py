import json
from typing import Optional

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import (
    AsyncJsonWebsocketConsumer,
    AsyncWebsocketConsumer,
)
from django.core.exceptions import ValidationError

from api.serializers.comment import CommentSerializer
from core.loggers import django_logger
from notifications.constants import MAX_NOTIFICATION_TEXT_LEN
from notifications.models import Notification, NotificationLevel
from users.models import Roles, User

from .constants import (
    MAX_COMMENT_TEXT_LEN,
    MAX_INCIDENT_COMMENTS_PER_PAGE,
)
from .models import (
    Comment,
    FavoritePriority,
    Incident,
    IncidentFavorite,
)


class WSCloseCode:
    """Коды закрытия WebSocket-соединения."""
    NORMAL = 1000
    AUTH_REQUIRED = 4001
    FORBIDDEN = 4003
    BAD_REQUEST = 4000
    INTERNAL_ERROR = 1011


class CommentConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.incident_id = self.scope['url_route']['kwargs']['incident_id']
        self.room_group_name = f'comments_{self.incident_id}'
        user: User = self.scope['user']

        if not user.is_authenticated or user.role == Roles.GUEST:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name, self.channel_name
        )
        await self.accept()

        await self.send_initial_history()

    async def disconnect(self, close_code: int):
        await self.channel_layer.group_discard(
            self.room_group_name, self.channel_name
        )

    @database_sync_to_async
    def get_comments_history(self):
        user: User = self.scope['user']

        queryset = (
            Comment.objects.filter(incident_id=self.incident_id)
            .select_related('author', 'incident')
            .order_by('-created_at', '-id')
            [:MAX_INCIDENT_COMMENTS_PER_PAGE]
        )

        is_admin = user.is_staff or user.is_superuser

        serializer_data = CommentSerializer(queryset, many=True).data

        for item in serializer_data:
            item['is_my_comment'] = (item['author_id'] == user.id)
            item['can_edit'] = is_admin or (item['author_id'] == user.id)

        author_ids = [item['author_id'] for item in serializer_data]
        if author_ids:
            authors = User.objects.filter(id__in=author_ids)
            author_map = {u.id: u for u in authors}

            for item in serializer_data:
                author_obj = author_map.get(item['author_id'])

                if author_obj:
                    if author_obj.get_avatar_url:
                        item['avatar_url'] = author_obj.get_avatar_url
                    else:
                        item['avatar_url'] = None
                else:
                    item['avatar_url'] = None
                item['username'] = author_obj.username

        return serializer_data

    async def send_initial_history(self):
        data = await self.get_comments_history()

        await self.send(text_data=json.dumps({
            'type': 'init_history',
            'data': data,
            'meta': {'sort_order': 'desc'}
        }))

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        payload = data.get('data', {})

        try:
            if action == 'create':
                comment = await self.create_comment(payload)
                await self.send_initial_update(comment, 'created')
            elif action == 'update':
                comment = await self.update_comment(payload)
                await self.send_initial_update(comment, 'updated')
            elif action == 'delete':
                await self.delete_comment(payload)
                await self.send_initial_history()

        except (ValidationError, PermissionError) as e:
            msg = e.message or e
            await self.send(
                text_data=json.dumps({'type': 'error', 'message': str(msg)})
            )

        except Exception as e:
            django_logger.exception(e)
            await self.send(
                text_data=json.dumps(
                    {'type': 'error', 'message': '500: Server Error'}
                )
            )

    async def send_initial_update(
        self, comment_instance: Comment, action_type: str
    ):
        user: User = self.scope['user']
        room_group_name = f'comments_{comment_instance.incident_id}'

        serializer = CommentSerializer(comment_instance)
        data = serializer.data

        data['is_my_comment'] = (data['author_id'] == user.id)
        is_admin = user.is_staff or user.is_superuser
        data['can_edit'] = is_admin or (data['author_id'] == user.id)

        if hasattr(comment_instance, 'author'):
            author: User = comment_instance.author
            if author.get_avatar_url:
                data['avatar_url'] = author.get_avatar_url
            else:
                data['avatar_url'] = None
            data['username'] = author.username
        else:
            data['avatar_url'] = None
            data['username'] = None

        await self.channel_layer.group_send(
            room_group_name,
            {
                'type': 'broadcast_update',
                'action': action_type,
                'payload': data
            }
        )

    @database_sync_to_async
    def create_comment(self, data):
        user: User = self.scope['user']
        content = str(data.get('content', '')).strip()

        if not content:
            raise ValidationError('Комментарий не может быть пустым')

        if len(content) > MAX_COMMENT_TEXT_LEN:
            raise ValidationError(
                f'Максимальная длина комментария - {MAX_COMMENT_TEXT_LEN} '
                'символов'
            )

        comment = Comment.objects.create(
            author=user, incident_id=self.incident_id, content=content
        )

        incident = (
            Incident.objects.only('id', 'was_read', 'responsible_user_id')
            .get(id=self.incident_id)
        )

        if (
            incident.was_read
            and incident.responsible_user_id != user.id
            and user.role != Roles.DISPATCH
        ):
            incident.was_read = False
            incident.save(update_fields=['was_read'])

        if (
            incident.responsible_user_id
            and incident.responsible_user_id != user.id
            and user.role != Roles.DISPATCH
        ):
            Notification.objects.create(
                user=incident.responsible_user,
                title=f'Новый комментарий от {user}',
                message=content[:MAX_NOTIFICATION_TEXT_LEN],
                level=NotificationLevel.MEDIUM,
                data={'incident_id': incident.id},
            )

        return comment

    @database_sync_to_async
    def update_comment(self, data):
        user: User = self.scope['user']
        comment_id = data.get('id')
        content = str(data.get('content', '')).strip()

        comment = Comment.objects.get(id=comment_id)

        is_admin = user.is_staff or user.is_superuser
        if comment.author != user and not is_admin:
            raise PermissionError(
                'Можно редактировать только свои комментарии.'
            )

        if not content:
            raise ValidationError('Комментарий не может быть пустым')

        if len(content) > MAX_COMMENT_TEXT_LEN:
            raise ValidationError(
                f'Максимальная длина комментария - {MAX_COMMENT_TEXT_LEN} '
                'символов'
            )

        comment.content = content
        comment.save()
        return comment

    @database_sync_to_async
    def delete_comment(self, data):
        user: User = self.scope['user']
        comment_id = data.get('id')

        comment = Comment.objects.get(id=comment_id)

        is_admin = user.is_staff or user.is_superuser
        if comment.author != user and not is_admin:
            raise PermissionError('Можно удалять только свои комментарии.')

        comment.delete()
        return True

    async def broadcast_update(self, event):
        user = self.scope['user']

        payload = event.get('payload', {})
        action = event.get('action')

        if action == 'deleted':
            await self.send(text_data=json.dumps({
                'type': 'update',
                'action': action,
                'payload': payload
            }))
            await self.send_initial_history()
            return

        author_id = payload['author_id']

        is_my_comment = (int(author_id) == user.id)

        is_admin = user.is_staff or user.is_superuser

        can_edit = is_admin or is_my_comment

        payload['is_my_comment'] = is_my_comment
        payload['can_edit'] = can_edit

        await self.send(text_data=json.dumps({
            'type': 'update',
            'action': action,
            'payload': payload
        }))


class IncidentFavoriteConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket для real-time управления избранным инцидентом.

    URL: /ws/incidents/incident-favorite/<int:incident_id>/
    Аутентификация: Django session (AuthMiddlewareStack).
    """

    user = None
    incident_id = None
    group_name = None

    async def connect(self):
        self.user = self.scope.get('user')

        if (
            self.user is None
            or not self.user.is_authenticated
            or getattr(self.user, 'role', None) == 'guest'
        ):
            await self.close(code=WSCloseCode.AUTH_REQUIRED)
            return

        self.incident_id = self.scope['url_route']['kwargs']['incident_id']
        self.group_name = f'incident_fav_{self.incident_id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code: int):
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content: Optional[dict] = None, **kwargs):
        if not content:
            return

        msg_type = content.get('type')

        if msg_type == 'toggle_favorite':
            await self._handle_toggle(content.get('is_favorite', True))
        elif msg_type == 'set_priority':
            await self._handle_set_priority(content.get('priority'))
        else:
            await self._send_error(f'Unknown type: {msg_type}')

    async def _handle_toggle(self, is_favorite: bool):
        try:
            if is_favorite:
                await self._create_favorite()
                priority = FavoritePriority.NORMAL
            else:
                is_favorite = await self._delete_favorite()
                priority = FavoritePriority.NORMAL

        except Exception as e:
            django_logger.exception(e)
            await self._send_error('500: Server Error')
            return

        await self._broadcast(is_favorite, priority)

    async def _handle_set_priority(self, priority: str):
        valid = [c[0] for c in FavoritePriority.choices]
        if priority not in valid:
            await self._send_error(f'Invalid priority. Valid: {valid}')
            return

        updated = await self._update_priority(priority)

        if not updated:
            await self._send_error('Not in favorites. Add first.')
            return

        await self._broadcast(True, priority)

    async def favorite_state_update(self, event: dict):
        await self.send_json({
            'type': 'state_update',
            'incident_id': str(event['incident_id']),
            'is_favorite': event['is_favorite'],
            'priority': event['priority'],
        })

    @sync_to_async
    def _create_favorite(self):
        """Создать запись избранного (в отдельном потоке)."""
        IncidentFavorite.objects.get_or_create(
            user=self.user,
            incident_id=self.incident_id,
        )

    @sync_to_async
    def _delete_favorite(self):
        """Удалить запись избранного (в отдельном потоке)."""
        favorite, created = IncidentFavorite.objects.get_or_create(
            user=self.user,
            incident_id=self.incident_id,
        )

        if not created:
            favorite.delete()
            return False

        return True

    @sync_to_async
    def _update_priority(self, priority: str) -> int:
        """Обновить приоритет. Возвращает количество изменённых строк."""
        return IncidentFavorite.objects.filter(
            user=self.user,
            incident_id=self.incident_id,
        ).update(priority=priority)

    async def _broadcast(self, is_favorite: bool, priority: str):
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'favorite.state_update',
                'incident_id': self.incident_id,
                'is_favorite': is_favorite,
                'priority': priority,
            },
        )

    async def _send_error(self, message: str):
        await self.send_json({
            'type': 'error',
            'message': message,
        })
