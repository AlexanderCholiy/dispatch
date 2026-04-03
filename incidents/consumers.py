# incidents/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Comment
from users.models import User, Roles
from api.serializers.comment import CommentSerializer
from core.loggers import django_logger
from django.db.models import Q
from django.core.exceptions import ValidationError

from .constants import MAX_INCIDENT_COMMENTS_PER_PAGE, MAX_COMMENT_TEXT_LEN


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
            .order_by('-created_at', '-id')[:MAX_INCIDENT_COMMENTS_PER_PAGE]
        )

        is_admin = user.is_staff or user.is_superuser

        if not is_admin:
            queryset = queryset.filter(
                Q(author=user) | Q(author__role=Roles.DISPATCH)
            )

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
                    if author_obj.avatar:
                        item['avatar_url'] = author_obj.avatar.url
                    else:
                        item['avatar_url'] = None
                else:
                    item['avatar_url'] = None

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
            author = comment_instance.author
            if hasattr(author, 'avatar') and author.avatar:
                data['avatar_url'] = author.avatar.url
            else:
                data['avatar_url'] = None
        else:
            data['avatar_url'] = None

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
        user = self.scope['user']
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
        await self.send(text_data=json.dumps({
            'type': 'update',
            'action': event['action'], 
            'payload': event['payload']
        }))
