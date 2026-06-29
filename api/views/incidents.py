from datetime import datetime
from http import HTTPStatus
from pathlib import Path

from django.db.models import Prefetch
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.constants import (
    ACTUAL_INCIDENTS_FILE,
    API_DATETIME_FORMAT,
    ARCHIVE_INCIDENTS_DIR
)
from api.filters import IncidentReportFilter
from api.pagination import IncidentReportPagination
from api.serializers.incidents import IncidentReportSerializer
from core.views import send_x_accel_file
from incidents.annotations import annotate_sla_dispatch
from incidents.models import Comment, Incident, IncidentStatusHistory
from ts.models import PoleContractorEmail
from users.models import Roles


class IncidentReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Возвращает подробную информации по инцидентам.

    ПОЛЯ:
    - code: Уникальный код инцидента.
    - last_status: Последний статус инцидента.
    - incident_type: Тип инцидента.
    - incident_subtype: Подтип инцидента.
    - categories: Категории инцидента.

    - incident_datetime: Дата и время возникновения инцидента (UTC, ISO).
    - incident_update_datetime: Дата и время обновления инцидента (UTC, ISO).
    - incident_finish_datetime: Дата и время завершения инцидента (UTC, ISO).

    - avr_names: Название подрядчика АВР.
    - avr_emails: Email-адреса подрядчика АВР.

    - avr_start_datetime: Дата и время начала АВР.
    - avr_end_datetime: Дата и время завершения АВР.
    - is_sla_avr_expired: Превышен ли SLA по АВР.
    - avr_deadline: Дедлайн SLA АВР.
    - avr_duration: Период АВР.

    - rvr_start_datetime: Дата и время начала РВР.
    - rvr_end_datetime: Дата и время завершения РВР.
    - is_sla_rvr_expired: Превышен ли SLA по РВР.
    - rvr_deadline: Дедлайн SLA РВР.
    - rvr_duration: Период РВР.

    - dgu_start_datetime: Дата и время начала ДГУ.
    - dgu_end_datetime: Дата и время завершения ДГУ.
    - is_vrt_dgu_expired: Превышает ли период дизеления 15 суток
    - dgu_deadline: Дедлайн ВРТ ДГУ.
    - dgu_duration: Период дизеления.

    - eks_start_datetime: Дата и время начала ЭКС.
    - eks_end_datetime: Дата и время завершения ЭКС.
    - is_vrt_eks_expired: Превышает ли период ЭКС 15 суток
    - eks_deadline: Дедлайн длительности ЭКС.
    - eks_duration: Период ЭКС.

    - pole: Шифр опоры.
    - region_ru: Регион опоры.
    - macroregion: Макрорегион опоры.

    - base_station: Базовая станция.
    - operator_group: Группа операторов базовой станции.

    - responsible_user_id: Идентификатор ответственного пользователя.
    - responsible_user_name: Имя ответственного пользователя в системе.
    - is_sla_dispatch_expired: Просрочен ли SLA диспетчера.
    - dispatch_sla_duration: Текущая длительность обработки заявки по SLA.

    - last_dispatch_comment_text: Последний комментарий диспетчера.
    - last_dispatch_comment_datetime: Дата и время последнего комментария
    диспетчера.

    ДОСТУПНЫЕ ЭНДПОИНТЫ:

    1) Пагинированный список инцидентов:
       GET /api/v1/reports/incidents/

    2) Фильтрация по последнему месяцу:
       GET /api/v1/reports/incidents/?last_month=true

    3) Выгрузка актуальных данных в CSV:
       GET /api/v1/reports/incidents/csv_export/
       (Файл: actual_incidents.csv)

    4) Список доступных архивных отчетов:
       GET /api/v1/reports/incidents/archives/
       (Возвращает JSON со списком файлов за годы и кварталы)

    5) Скачивание конкретного архива:
       GET /api/v1/reports/incidents/<filename>/
    """
    queryset = Incident.objects.select_related(
        'incident_type',
        'incident_subtype',
        'pole',
        'pole__avr_contractor',
        'base_station',
        'responsible_user',
        'pole__region',
        'pole__region__macroregion',
    ).prefetch_related(
        'base_station__operator',
        'statuses',
        'categories',
        Prefetch(
            'pole__pole_emails',
            queryset=PoleContractorEmail.objects.select_related(
                'email', 'contractor'
            ),
        ),
        Prefetch(
            'status_history',
            queryset=(
                IncidentStatusHistory.objects
                .select_related('status')
                .order_by('insert_date', 'id')
            ),
            to_attr='prefetched_statuses'
        ),
        Prefetch(
            'comments',
            queryset=Comment.objects.filter(
                author__role=Roles.DISPATCH.value
            ).order_by('-created_at', '-id'),
            to_attr='last_dispatch_comments'
        ),
    )
    queryset = annotate_sla_dispatch(queryset)

    serializer_class = IncidentReportSerializer
    permission_classes = (permissions.AllowAny,)
    filter_backends = (
        DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter
    )
    filterset_class = IncidentReportFilter
    pagination_class = IncidentReportPagination

    search_fields = ('=code',)

    ordering_fields = ('incident_date', 'id')
    ordering = ('-incident_date', '-id')

    @action(detail=False, methods=['get'], url_path='csv_export')
    def csv_export(self, request: Request):
        """
        Выгрузка CSV файла с актуальными инцидентами.
        Файл генерируется фоновой задачей Celery.
        Если файл еще не сформирован, возвращается ошибка 503.
        """
        response = self._get_cached_file_response(ACTUAL_INCIDENTS_FILE)
        if response:
            return response

        return HttpResponse(
            'Файл отчета еще не сформирован или обновляется.',
            status=HTTPStatus.SERVICE_UNAVAILABLE
        )

    def _get_cached_file_response(self, cache_file: Path):
        """
        Проверяет существование файла.
        Возвращает HttpResponse с X-Accel-Redirect, если файл существует.
        Иначе возвращает None.
        """
        if not cache_file.exists():
            return None
        return send_x_accel_file(cache_file)

    @action(detail=False, methods=['get'], url_path='archives')
    def archives(self, request: Request):
        """
        Возвращает JSON со списком доступных архивных отчетов.
        Файлы должны лежать в ARCHIVE_INCIDENTS_DIR с именами вида:
        archive_{year}_Q{quarter}_incidents.csv
        """
        archives = []

        if not ARCHIVE_INCIDENTS_DIR.exists():
            return Response({'archives': []})

        files = sorted(ARCHIVE_INCIDENTS_DIR.glob("*.csv"), reverse=True)

        for file in files:
            name = file.stem
            # Ожидаем формат: archive_YYYY_QN_incidents
            parts = name.split('_')

            year = None
            quarter = None

            if len(parts) >= 3 and parts[0] == 'archive':
                try:
                    year = parts[1]
                    quarter_part = parts[2]
                    if quarter_part.startswith('Q'):
                        quarter = quarter_part.replace('Q', '')
                except (IndexError, ValueError):
                    pass

            mtime_timestamp = file.stat().st_mtime
            updated_at_dt = datetime.fromtimestamp(
                mtime_timestamp, tz=timezone.get_current_timezone()
            )

            updated_at_str = updated_at_dt.strftime(API_DATETIME_FORMAT)

            archives.append({
                'year': year,
                'quarter': quarter,
                'filename': file.name,
                'url': (
                    f'/api/v1/reports/incidents/{file.name}/'
                ),
                'size_bytes': file.stat().st_size,
                'updated_at': updated_at_str,
            })

        return Response({'archives': archives})

    @action(
        detail=False,
        methods=['get'],
        url_path=r'(?P<filename>.+\.csv)'
    )
    def download_archive(self, request: Request, filename: str):
        """Скачивание конкретного архивного файла по имени."""
        file_path = ARCHIVE_INCIDENTS_DIR / filename

        if not file_path.exists():
            return HttpResponse(
                'Отчет не найден', status=HTTPStatus.NOT_FOUND
            )

        return send_x_accel_file(file_path)
