import json
from channels.generic.websocket import AsyncWebsocketConsumer


class CommentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.incident_id = self.scope['url_route']['kwargs']['incident_id']
        self.room_group_name = f'comments_{self.incident_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def comment_event(self, event):
        event_type = event['event_type']
        data = event['data']

        await self.send(text_data=json.dumps({
            'type': 'update',
            'action': event_type,
            'payload': data
        }))
