import asyncio
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.urls import reverse
from asgiref.sync import sync_to_async
from rest_framework.test import APIRequestFactory, force_authenticate
from core.loggers import django_logger
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .constants import STATS_INTERVAL_SECONDS


class IncidentStatsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.running = True
        self.task = asyncio.create_task(self.send_statistics_loop())

    async def disconnect(self, close_code: int):
        self.running = False
        if hasattr(self, 'task'):
            self.task.cancel()

    async def send_statistics_loop(self):
        while self.running:
            try:
                data = await self.get_statistics()
                await self.send(text_data=json.dumps(data))
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

        request_all = factory.get(url)
        force_authenticate(request_all, user=None)
        response_all = view(request_all)

        now = timezone.localtime()
        first_day_prev_month = (
            now.replace(day=1) - relativedelta(months=1)
        ).date()

        request_month = factory.get(url, {
            'start_date': first_day_prev_month.isoformat(),
            'end_date': now.date().isoformat(),
        })
        force_authenticate(request_month, user=None)
        response_month = view(request_month)

        return {
            'all_period': response_all.data,
            'current_month': response_month.data,
            'meta': {
                'generated_at': now.isoformat(),
                'period': {
                    'from': first_day_prev_month.isoformat(),
                    'to': now.date().isoformat(),
                }
            }
        }
