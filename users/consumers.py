import re
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from users.models import User, Roles
from asgiref.sync import sync_to_async

from users.services.presence import PresenceService


class PresenceConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket Consumer для отслеживания присутствия пользователей."""

    @staticmethod
    def _get_page_group_name(url: str) -> str:
        """Генерирует безопасное имя группы для конкретной страницы."""
        clean_url = url.split('?')[0]
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', clean_url)

        # Ограничиваем длину (Channels требует < 100 символов)
        if len(safe_name) > 80:
            safe_name = safe_name[:80]

        return f'presence_page_{safe_name}'

    async def connect(self):
        self.user: User = self.scope['user']

        if not self.user.is_authenticated or self.user.role == Roles.GUEST:
            await self.close()
            return

        await self.accept()

    async def disconnect(self, close_code: int):
        await sync_to_async(PresenceService.remove_user)(self.user)

    async def receive_json(self, content: dict):
        msg_type = content.get('type')
        url = content.get('url')
        old_url = content.get('old_url')

        if not url or not isinstance(url, str):
            return

        group_name = self._get_page_group_name(url)

        # 1. Обновляем присутствие в Redis
        await sync_to_async(
            PresenceService.update_presence
        )(self.user, url)

        if msg_type == 'page_change':
            # 2. Обрабатываем уход со старой страницы
            if old_url and isinstance(old_url, str):
                old_group_name = self._get_page_group_name(old_url)
                await sync_to_async(
                    PresenceService.remove_user_from_page
                )(self.user, old_url)
                await self.channel_layer.group_discard(
                    old_group_name, self.channel_name
                )

        await self.channel_layer.group_add(group_name, self.channel_name)

        # 3. Получаем данные пользователей на странице:
        users_list = await sync_to_async(PresenceService.get_users_on_page)(
            url
        )

        broadcast_data = {
            'type': 'users_list',
            'url': url,
            'users': users_list
        }

        await self.channel_layer.group_send(group_name, {
            'type': 'presence_update',
            'data': broadcast_data
        })

    async def presence_update(self, event: dict):
        data = event['data']
        await self.send_json(data)
