import asyncio
import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from core.loggers import django_logger

from .constants import STATS_INTERVAL_SECONDS


class IncidentStatsConsumer(AsyncWebsocketConsumer):

    _last_data = None

    async def connect(self):
        await self.accept()
        self.running = True

        if self._last_data:
            await self.send(text_data=json.dumps(self._last_data))

        self.task = asyncio.create_task(self.send_statistics_loop())

    async def disconnect(self, close_code: int):
        self.running = False
        if hasattr(self, 'task'):
            self.task.cancel()

    async def send_statistics_loop(self):
        while self.running:
            try:
                data = await self.get_statistics()
                if data != self._last_data:
                    await self.send(text_data=json.dumps(data))
                    self._last_data = data

            except Exception as e:
                django_logger.debug(e, exc_info=True)
                await self.send(text_data=json.dumps({
                    'error': 'Failed to load statistics'
                }))

            await asyncio.sleep(STATS_INTERVAL_SECONDS)

    async def get_statistics(self):
        """
        Получаем статистику за два периода:
        1) весь период (без фильтра)
        2) с первого числа предыдущего месяца по текущий день
        """
        return await sync_to_async(self._fetch_statistics)()

    def _fetch_statistics(self):
        """
        Синхронный код для вызова DRF ViewSet через внутренний GET-запрос.
        """
        from api.views import StatisticReportViewSet

        factory = APIRequestFactory()
        view = StatisticReportViewSet.as_view({'get': 'list'})
        url = reverse('statistics_report-list')

        now = timezone.localtime()
        first_day_prev_month = (
            now.replace(day=1) - relativedelta(months=1)
        ).date()

        request_month = factory.get(url, {
            'start_date': first_day_prev_month.isoformat(),
        })
        force_authenticate(request_month, user=None)
        response_month = view(request_month)

        return {
            'period': response_month.data,
            'meta': {
                'generated_at': now.isoformat(),
                'period': {
                    'from': first_day_prev_month.isoformat(),
                    'to': now.date().isoformat(),
                }
            }
        }
