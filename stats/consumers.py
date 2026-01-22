import asyncio
import json
from http import HTTPStatus
from typing import Optional

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from core.loggers import django_logger

from .constants import STATS_INTERVAL_SECONDS


class IncidentStatsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer для отправки статистики инцидентов.

    Поддерживаемые параметры от клиента (JSON):
    - start_date (YYYY-MM-DD, optional)
    - end_date (YYYY-MM-DD, optional)
    - monitoring_check (bool, optional)

    Если параметры не переданы, используются значения по умолчанию:
    - start_date: первый день предыдущего месяца
    - end_date: сегодня
    - monitoring_check: False
    """

    async def connect(self):
        await self.accept()
        self.running = True
        self._last_data = None
        self.query_params = {}

        self.task = asyncio.create_task(self.send_statistics_loop())

    async def disconnect(self, close_code: int):
        self.running = False
        if hasattr(self, 'task'):
            self.task.cancel()

    async def receive(
        self,
        text_data: Optional[str] = None,
        bytes_data: Optional[bytes] = None,
    ):
        """Обновление параметров запроса, присланных клиентом"""
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'error': 'Invalid JSON'}))
            return

        self.query_params = payload

        data = await self.get_statistics()
        await self.send(text_data=json.dumps(data))

    async def send_statistics_loop(self):
        while self.running:
            try:
                data = await self.get_statistics()
                await self.send(text_data=json.dumps(data))
            except Exception as e:
                django_logger.debug(e, exc_info=True)

            await asyncio.sleep(STATS_INTERVAL_SECONDS)

    async def get_statistics(self):
        """
        Получаем статистику через синхронный ViewSet с query params
        """
        return await sync_to_async(self._fetch_statistics)(self.query_params)

    def _fetch_statistics(self, params: dict = None):
        """
        Синхронный вызов DRF ViewSet для получения статистики с query params.
        Любые ошибки валидации (например, неверный формат дат) ловятся и
        возвращаются клиенту в JSON.
        """
        from api.views import StatisticReportViewSet

        factory = APIRequestFactory()
        view = StatisticReportViewSet.as_view({'get': 'list'})
        url = reverse('statistics_report-list')

        now = timezone.localtime()
        first_day_prev_month = (
            now.replace(day=1) - relativedelta(months=1)
        ).date()

        # Дефолтные параметры
        query = {
            'start_date': first_day_prev_month.isoformat(),
            'end_date': now.date().isoformat(),
            'monitoring_check': False,
        }

        if params:
            if 'start_date' in params:
                query['start_date'] = params['start_date']
            if 'end_date' in params:
                query['end_date'] = params['end_date']
            if 'monitoring_check' in params:
                query['monitoring_check'] = (
                    str(params['monitoring_check']).lower()
                    in ('1', 'true', 'yes')
                )

        request = factory.get(url, query)
        force_authenticate(request, user=None)

        try:
            response = view(request)
            data = response.data
        except Exception as e:
            django_logger.debug(e, exc_info=True)
            return {
                'error': str(e),
                'status_code': HTTPStatus.BAD_REQUEST,
                'query': query
            }

        if getattr(
            response, 'status_code', HTTPStatus.OK
        ) >= HTTPStatus.BAD_REQUEST:
            return {
                'error': data,
                'status_code': response.status_code,
                'query': query
            }

        return {
            'period': data,
            'meta': {
                'generated_at': now.isoformat(),
                'period': {
                    'from': query['start_date'],
                    'to': query['end_date'],
                },
                'query': query,
            }
        }
