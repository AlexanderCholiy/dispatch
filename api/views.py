import json
from datetime import date, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Optional

from django.core.cache import cache
from django.db.models import (
    Count,
    Exists,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
)
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from redis.exceptions import LockError
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle

from core.views import send_x_accel_file
from incidents.annotations import (
    annotate_is_power_issue,
    annotate_sla_avr,
    annotate_sla_rvr,
)
from incidents.constants import NOTIFIED_CONTRACTOR_STATUS_NAME
from incidents.models import Incident, IncidentStatusHistory
from ts.models import MacroRegion, PoleContractorEmail

from .constants import (
    ALL_CLOSED_INCIDENT_AGE_LIMIT,
    BASE_INCIDENT_VALID_FILTER,
    CACHE_INCIDENTS_FILE,
    CACHE_INCIDENTS_LAST_MONTH_FILE,
    CACHE_INCIDENTS_TTL,
    CLOSED_INCIDENTS_VALID_FILTER,
    JSON_EXPORT_CHUNK_SIZE,
    OPEN_INCIDENTS_VALID_FILTER,
    STATISTIC_CACHE_TIMEOUT,
    TOTAL_VALID_INCIDENTS_FILTER,
)
from .filters import IncidentReportFilter
from .pagination import IncidentReportPagination
from .serializers import IncidentReportSerializer, StatisticReportSerializer
from .utils import get_first_day_prev_month
from .validators import validate_date_range


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
    - incident_finish_datetime: Дата и время завершения инцидента (UTC, ISO).

    - avr_start_datetime: Дата и время начала АВР.
    - avr_end_datetime: Дата и время завершения АВР.
    - is_sla_avr_expired: Превышен ли SLA по АВР.
    - avr_deadline: Дедлайн SLA АВР.
    - avr_names: Название подрядчика АВР.
    - avr_emails: Email-адреса подрядчика АВР.

    - rvr_start_datetime: Дата и время начала РВР.
    - rvr_end_datetime: Дата и время завершения РВР.
    - is_sla_rvr_expired: Превышен ли SLA по РВР.
    - rvr_deadline: Дедлайн SLA РВР.

    - pole: Шифр опоры.
    - region_ru: Регион опоры.
    - macroregion: Макрорегион опоры.

    - base_station: Базовая станция.
    - operator_group: Группа операторов базовой станции.

    ДОСТУПНЫЕ ЭНДПОИНТЫ:

    1) Пагинированный список инцидентов:
       GET /api/v1/report/incidents/

    2) Фильтрация по последнему месяцу:
       GET /api/v1/report/incidents/?last_month=true

    3) Полная выгрузка для JSON (без пагинации):
       GET /api/v1/report/incidents/json_export/

    4) Полная выгрузка за последний месяц:
       GET /api/v1/report/incidents/json_export/?last_month=true
    """
    queryset = Incident.objects.all().select_related(
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
                .order_by('insert_date')
            ),
            to_attr='prefetched_statuses'
        ),
    )

    serializer_class = IncidentReportSerializer
    permission_classes = (permissions.AllowAny,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = IncidentReportFilter
    pagination_class = IncidentReportPagination
    ordering_fields = ('incident_date', 'id')
    ordering = ('-incident_date', '-id')

    def get_queryset(self) -> QuerySet:
        qs = super().get_queryset()

        closed_last_year_filter = BASE_INCIDENT_VALID_FILTER & Q(
            is_incident_finish=True,
            incident_finish_date__isnull=False,
            incident_finish_date__gte=(
                timezone.now() - ALL_CLOSED_INCIDENT_AGE_LIMIT
            )
        )

        return qs.filter(
            OPEN_INCIDENTS_VALID_FILTER | closed_last_year_filter
        )

    @action(detail=False, methods=['get'], url_path='json_export')
    def json_export(self, request: Request):
        """
        Полная выгрузка инцидентов ввиде .json без пагинации с кешированием 5
        мин.
        """
        self.pagination_class = None

        last_month = (
            request.query_params.get('last_month', '').lower()
        ) == 'true'

        cache_file = (
            CACHE_INCIDENTS_LAST_MONTH_FILE
            if last_month else CACHE_INCIDENTS_FILE
        )

        response = self._get_cached_file_response(cache_file)
        if response:
            return response

        lock_key = f'lock__{cache_file.name}'

        try:
            with cache.lock(lock_key, timeout=600, blocking_timeout=60):
                response = self._get_cached_file_response(cache_file)
                if response:
                    return response

                queryset = self.get_queryset()
                if last_month:
                    queryset = queryset.filter(
                        incident_date__gte=get_first_day_prev_month()
                    )

                tmp_file = cache_file.with_suffix('.tmp')
                try:
                    with tmp_file.open('w', encoding='utf-8') as f:
                        for chunk in self._stream_json_chunks(queryset):
                            f.write(chunk)
                    tmp_file.replace(cache_file)
                finally:
                    if tmp_file.exists():
                        tmp_file.unlink()

                return send_x_accel_file(cache_file)

        except LockError:
            return HttpResponse(
                'Файл все еще генерируется, попробуйте позже.',
                status=HTTPStatus.SERVICE_UNAVAILABLE
            )

    def _stream_json_chunks(self, qs: QuerySet):
        """Потоковая сериализация JSON по блокам."""
        yield '['
        first = True
        chunk = []
        for obj in qs.iterator():
            chunk.append(self.get_serializer(obj).data)
            if len(chunk) >= JSON_EXPORT_CHUNK_SIZE:
                for item in chunk:
                    if first:
                        first = False
                    else:
                        yield ','
                    yield json.dumps(item, ensure_ascii=False)
                chunk = []
        # Последний неполный блок:
        if chunk:
            for item in chunk:
                if first:
                    first = False
                else:
                    yield ','
                yield json.dumps(item, ensure_ascii=False)
        yield ']'

    def _get_cached_file_response(
        self, cache_file: Path
    ) -> Optional[HttpResponse]:
        """Возвращает Response с файлом, если он существует и актуален."""
        if cache_file.exists():
            modified_time = datetime.fromtimestamp(
                cache_file.stat().st_mtime,
                tz=timezone.get_current_timezone()
            )
            if timezone.now() - modified_time < CACHE_INCIDENTS_TTL:
                return send_x_accel_file(cache_file)
        return None


class StatisticReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Возвращает статистику по макрорегионам.
    Статистика формируется на основе инцидентов и агрегируется
    по макрорегионам, связанным через регионы и опоры.

    ПОЛЯ:

    - macroregion: название макрорегиона региона
    - total_incidents: общее количество инцидентов (закрытых + открытых)
    - total_closed_incidents: количество закрытых инцидентов
    - total_open_incidents: количество открытых инцидентов
    - active_contractor_incidents: количество активных инцидентов, где
    уведомлены подрядчики или начат АВР/РВР
    - daily_incidents: разбивка количества инцидентов по дням
    в формате {"YYYY-MM-DD": количество}, включает все инциденты за период

    ПРОБЛЕМЫ С ПИТАНИЕМ:
    - open_incidents_with_power_issue:
        количество открытых инцидентов, у которых выявлена проблема с питанием.
    - closed_incidents_with_power_issue:
        количество закрытых инцидентов с проблемой по питанию.

    По умолчанию проверка по системе мониторинга ОТКЛЮЧЕНА, так как она требует
    обращения к сторонней БД и может значительно замедлять выполнение запроса.

    Для включения проверки мониторинга необходимо передать
    query-параметр:
        monitoring_check=true


    SLA АВР:
    - sla_avr_expired: количество инцидентов, где SLA АВР просрочена
    - sla_avr_closed_on_time: количество инцидентов, где SLA АВР
    выполнена вовремя
    - sla_avr_less_than_hour: количество инцидентов, где до SLA АВР осталось
    меньше часа
    - sla_avr_in_progress: количество инцидентов с АВР в процессе и SLA еще не
    истекла

    SLA РВР:
    - sla_rvr_expired: количество инцидентов, где SLA РВР просрочена
    - sla_rvr_closed_on_time: количество инцидентов, где SLA РВР
    выполнена вовремя
    - sla_rvr_less_than_hour: количество инцидентов, где до SLA РВР осталось
    меньше часа
    - sla_rvr_in_progress: количество инцидентов с РВР в процессе и SLA еще
    не истекла

    Query-параметры:

    - start_date (YYYY-MM-DD):
        Начальная дата инцидента (включительно).
        Если не указана — фильтрация снизу не применяется.

    - end_date (YYYY-MM-DD):
        Конечная дата инцидента (включительно).
        Если не указана — фильтрация сверху не применяется.

    - monitoring_check (bool, default=false):
        Включает дополнительную проверку проблемы питания по данным
        мониторинга (сторонняя БД). Если false — используется только
        эвристика по типу инцидента и данным инцидента.

    ПРИМЕРЫ ЗАПРОСОВ:
    Получить статистику за всё время:
        GET /api/v1/report/statistics/

    Получить статистику с указанной даты:
        GET /api/v1/report/statistics/?start_date=2025-01-01

    Получить статистику до указанной даты:
        GET /api/v1/report/statistics/?end_date=2025-01-31

    Получить статистику за период:
        GET /api/v1/report/statistics/?start_date=2025-01-01&end_date=
        2025-01-31
    """
    serializer_class = StatisticReportSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'stats_request'

    def get_queryset(self) -> QuerySet:
        params = self.request.query_params

        start, end = validate_date_range(
            params.get('start_date'),
            params.get('end_date'),
        )

        monitoring_check = params.get('monitoring_check', 'false').lower() in (
            '1', 'true', 'yes'
        )

        cache_key = self._build_statistic_cache_key(
            start, end, monitoring_check
        )
        cached = cache.get(cache_key)

        if cached:
            return cached

        incident_date_filter = self._get_incident_date_filter(start, end)

        incidents = (
            Incident.objects
            .filter(TOTAL_VALID_INCIDENTS_FILTER)
            .filter(incident_date_filter)
            .select_related('pole', 'incident_type')
        )

        # -------- EXISTS вместо JOIN --------
        notified_exists = IncidentStatusHistory.objects.filter(
            incident_id=OuterRef('pk'),
            status__name=NOTIFIED_CONTRACTOR_STATUS_NAME
        )
        incidents = incidents.annotate(
            has_notified_contractor=Exists(notified_exists)
        )

        # -------- SLA аннотации --------
        incidents = annotate_sla_avr(incidents)
        incidents = annotate_sla_rvr(incidents)

        # -------- Агрегация --------
        incident_stats = (
            incidents
            .values('pole__region__macroregion')
            .annotate(
                total_closed_incidents=Count(
                    'id', distinct=True, filter=CLOSED_INCIDENTS_VALID_FILTER
                ),
                total_open_incidents=Count(
                    'id', distinct=True, filter=OPEN_INCIDENTS_VALID_FILTER
                ),
                active_contractor_incidents=Count(
                    'id',
                    distinct=True,
                    filter=(
                        OPEN_INCIDENTS_VALID_FILTER
                        & (
                            Q(has_notified_contractor=True)
                            | Q(avr_start_date__isnull=False)
                            | Q(rvr_start_date__isnull=False)
                        )
                    )
                ),
                sla_avr_expired_count=Count(
                    'id', distinct=True, filter=Q(sla_avr_expired=True)
                ),
                sla_avr_closed_on_time_count=Count(
                    'id', distinct=True, filter=Q(sla_avr_closed_on_time=True)
                ),
                sla_avr_less_than_hour_count=Count(
                    'id', distinct=True, filter=Q(sla_avr_less_than_hour=True)
                ),
                sla_avr_in_progress_count=Count(
                    'id', distinct=True, filter=Q(sla_avr_in_progress=True)
                ),
                sla_rvr_expired_count=Count(
                    'id', distinct=True, filter=Q(sla_rvr_expired=True)
                ),
                sla_rvr_closed_on_time_count=Count(
                    'id', distinct=True, filter=Q(sla_rvr_closed_on_time=True)
                ),
                sla_rvr_less_than_hour_count=Count(
                    'id', distinct=True, filter=Q(sla_rvr_less_than_hour=True)
                ),
                sla_rvr_in_progress_count=Count(
                    'id', distinct=True, filter=Q(sla_rvr_in_progress=True)
                ),
            )
        )

        # Отдельно считаем открытые и закрытые с проблемой питания
        power_qs = annotate_is_power_issue(
            incidents, monitoring_check=monitoring_check
        ).filter(is_power_issue=True)

        open_power_map = {
            row['pole__region__macroregion']: row['c']
            for row in (
                power_qs
                .filter(OPEN_INCIDENTS_VALID_FILTER)
                .values('pole__region__macroregion')
                .annotate(c=Count('id', distinct=True))
            )
        }

        closed_power_map = {
            row['pole__region__macroregion']: row['c']
            for row in (
                power_qs
                .filter(CLOSED_INCIDENTS_VALID_FILTER)
                .values('pole__region__macroregion')
                .annotate(c=Count('id', distinct=True))
            )
        }

        stats_map = {
            item['pole__region__macroregion']: item for item in incident_stats
        }

        macroregions = list(MacroRegion.objects.order_by('name', 'id'))

        # -------- Считаем инциденты по дням --------
        daily_qs = (
            incidents
            .annotate(day=TruncDate('incident_date'))
            .values('pole__region__macroregion', 'day')
            .annotate(count=Count('id'))
            .order_by('pole__region__macroregion', 'day')
        )

        daily_map = {}
        for row in daily_qs:
            macro_id = row['pole__region__macroregion']
            day = row['day']
            count = row['count']
            daily_map.setdefault(macro_id, {})[day] = count

        # -------- Заполняем макрорегионы данными --------
        for macro in macroregions:
            macro_stats = stats_map.get(macro.pk, {})
            for field in [
                'total_closed_incidents',
                'total_open_incidents',
                'active_contractor_incidents',

                'sla_avr_expired_count',
                'sla_avr_closed_on_time_count',
                'sla_avr_less_than_hour_count',
                'sla_avr_in_progress_count',

                'sla_rvr_expired_count',
                'sla_rvr_closed_on_time_count',
                'sla_rvr_less_than_hour_count',
                'sla_rvr_in_progress_count',
            ]:
                setattr(macro, field, macro_stats.get(field, 0))

            macro.open_incidents_with_power_issue = open_power_map.get(
                macro.pk, 0
            )
            macro.closed_incidents_with_power_issue = closed_power_map.get(
                macro.pk, 0
            )

            macro.daily_incidents = daily_map.get(macro.pk, {})

        cache.set(cache_key, macroregions, STATISTIC_CACHE_TIMEOUT)

        return macroregions

    def _get_incident_date_filter(
        self, start: Optional[date], end: Optional[date]
    ) -> Q:
        q = Q()

        if start:
            q &= Q(incident_date__date__gte=start)
        if end:
            q &= Q(incident_date__date__lte=end)

        return q

    def _build_statistic_cache_key(
        self,
        start: Optional[date],
        end: Optional[date],
        monitoring_check: bool,
    ) -> str:
        start_key = start.isoformat() if start else 'none'
        end_key = end.isoformat() if end else 'none'
        monitoring_key = 'mon1' if monitoring_check else 'mon0'
        return f'statistic_report:{start_key}:{end_key}:{monitoring_key}'
