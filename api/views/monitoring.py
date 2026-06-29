from http import HTTPStatus
from pathlib import Path

from django.http import HttpResponse
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request

from core.views import send_x_accel_file
from monitoring.constants import SMS_RVR_CSV_FILE


class SMSCsvExportView(viewsets.ViewSet):
    """
    Экспорт CSV файла с оповещениями по СМС о проведении РВР.
    """
    permission_classes = (permissions.AllowAny,)

    @action(detail=False, methods=['get'], url_path='csv-export')
    def export_csv(self, request: Request):
        """Выгрузка CSV файла."""

        response = self._get_cached_file_response(SMS_RVR_CSV_FILE)
        if response:
            return response

        return HttpResponse(
            'Файл отчета еще не сформирован или обновляется.',
            status=HTTPStatus.SERVICE_UNAVAILABLE
        )

    def _get_cached_file_response(self, cache_file: Path):
        """
        Проверяет, существует ли файл.
        Возвращает HttpResponse с X-Accel-Redirect, если да.
        """
        if not cache_file.exists():
            return None

        return send_x_accel_file(cache_file)
