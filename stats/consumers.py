import asyncio
import json
import random

from channels.generic.websocket import AsyncWebsocketConsumer


class RandomNumberConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.running = True
        asyncio.create_task(self.send_random_numbers())

    async def disconnect(self, close_code):
        self.running = False

    async def send_random_numbers(self):
        while self.running:
            number = random.randint(1, 100)
            await self.send(text_data=json.dumps({'number': number}))
            await asyncio.sleep(1)
