from datetime import date
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
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle

from incidents.annotations import (
    annotate_is_power_issue,
    annotate_sla_avr,
    annotate_sla_rvr,
)
from incidents.constants import NOTIFIED_CONTRACTOR_STATUS_NAME
from incidents.models import Incident, IncidentStatusHistory
from ts.models import MacroRegion, PoleContractorEmail

from .constants import (
    CLOSED_INCIDENTS_VALID_FILTER,
    OPEN_INCIDENTS_VALID_FILTER,
    STATISTIC_CACHE_TIMEOUT,
    TOTAL_VALID_INCIDENTS_FILTER,
)
from .filters import IncidentReportFilter
from .pagination import IncidentReportPagination
from .serializers import IncidentReportSerializer, StatisticReportSerializer
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

    Доступна фильтрация:
    - по дате инцидента начиная с первого числа предыдущего месяца
      по текущее число:
      GET /api/v1/report/incidents/?last_month=true

    - получение всех инцидентов без пагинации:
      GET /api/v1/report/incidents/?all=true

    - Возвращает все инциденты за последний месяц без пагинации:
      GET /api/v1/report/incidents/?last_month=true&all=true
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

    def get_queryset(self):
        """Если передан all=true, возвращаем все записи без пагинации"""
        qs = super().get_queryset()
        self.request: Request
        if self.request.query_params.get('all', '').lower() == 'true':
            self.pagination_class = None
        return qs


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
    - open_incidents_with_power_issue: количество открытых инцидентов, у
    которых выявлена проблема с питанием на опоре с проверкой по мониторингу
    - closed_incidents_with_power_issue: количество закрытых инцидентов, у
    которых выявлена проблема с питанием на опоре с проверкой по мониторингу
    - daily_incidents: разбивка количества инцидентов по дням
    в формате {"YYYY-MM-DD": количество}, включает все инциденты за период

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

    ФИЛЬТРАЦИЯ ПО ДАТЕ:
    Поддерживается фильтрация по дате инцидента.

    Поддерживаемые query-параметры:

    - start_date (YYYY-MM-DD):
        Начальная дата инцидента (включительно).
        Если не указана — фильтрация снизу не применяется.

    - end_date (YYYY-MM-DD):
        Конечная дата инцидента (включительно).
        Если не указана — фильтрация сверху не применяется.

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

        cache_key = self._build_statistic_cache_key(start, end)
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
            incidents, monitoring_check=True
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
        self, start: Optional[date], end: Optional[date]
    ) -> str:
        start_key = start.isoformat() if start else 'none'
        end_key = end.isoformat() if end else 'none'
        return f'statistic_report:{start_key}:{end_key}'
