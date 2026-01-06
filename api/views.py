from datetime import date, timedelta
from typing import Optional

from django.core.cache import cache
from django.db.models import (
    Count,
    F,
    FilteredRelation,
    Prefetch,
    Q,
    QuerySet,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.request import Request

from incidents.annotations import annotate_sla_avr, annotate_sla_rvr
from incidents.constants import NOTIFIED_CONTRACTOR_STATUS_NAME
from incidents.models import Incident, IncidentStatusHistory
from ts.models import MacroRegion, PoleContractorEmail

from .constants import STATISTIC_CACHE_TIMEOUT
from .filters import IncidentReportFilter
from .pagination import IncidentReportPagination
from .serializers import IncidentReportSerializer, StatisticReportSerializer
from .validators import validate_date_range


class IncidentReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Возвращает подробную информации по инцидентам.

    Доступна фильтрация по дате инцидента начиная с первого числа предыдущего
    месяца по текущее число. GET: api/v1/incidents/?last_month=true
    """
    queryset = Incident.objects.all().select_related(
        'incident_type',
        'pole',
        'pole__avr_contractor',
        'base_station',
        'responsible_user',
        'pole__region',
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

        incidents = self.filter_queryset(
            Incident.objects
            .select_related('pole', 'incident_type')
            .filter(incident_date_filter)
        )

        incidents = annotate_sla_avr(incidents)
        incidents = annotate_sla_rvr(incidents)

        macroregion_sla_counts = (
            incidents.values('pole__region__macroregion')
            .annotate(
                sla_avr_expired_count=Count(
                    'id', filter=Q(sla_avr_expired=True)
                ),
                sla_avr_closed_on_time_count=Count(
                    'id', filter=Q(sla_avr_closed_on_time=True)
                ),
                sla_avr_less_than_hour_count=Count(
                    'id', filter=Q(sla_avr_less_than_hour=True)
                ),
                sla_avr_in_progress_count=Count(
                    'id', filter=Q(sla_avr_in_progress=True)
                ),
                sla_rvr_expired_count=Count(
                    'id', filter=Q(sla_rvr_expired=True)
                ),
                sla_rvr_closed_on_time_count=Count(
                    'id', filter=Q(sla_rvr_closed_on_time=True)
                ),
                sla_rvr_less_than_hour_count=Count(
                    'id', filter=Q(sla_rvr_less_than_hour=True)
                ),
                sla_rvr_in_progress_count=Count(
                    'id', filter=Q(sla_rvr_in_progress=True)
                ),
            )
        )

        sla_map = {
            item['pole__region__macroregion']: item
            for item in macroregion_sla_counts
        }

        dt = timedelta(hours=1)

        macroregion_incident_filter = self._get_macroregion_incident_filter(
            start, end
        )

        base_qs = (
            MacroRegion.objects
            .annotate(
                incidents_filtered=FilteredRelation(
                    'regions__poles__incidents',
                    condition=macroregion_incident_filter
                )
            )
            .annotate(
                total_closed_incidents=Count(
                    'incidents_filtered',
                    filter=Q(
                        incidents_filtered__code__isnull=False,
                        incidents_filtered__is_incident_finish=True,
                        incidents_filtered__incident_finish_date__isnull=False,
                        incidents_filtered__incident_finish_date__gt=(
                            F('incidents_filtered__incident_date') + dt
                        ),
                    ),
                    distinct=True
                ),
                total_open_incidents=Count(
                    'incidents_filtered',
                    filter=Q(
                        incidents_filtered__code__isnull=False,
                        incidents_filtered__is_incident_finish=False,
                    ),
                    distinct=True
                ),
                active_contractor_incidents=Count(
                    'incidents_filtered',
                    filter=Q(
                        incidents_filtered__is_incident_finish=False
                    ) & (
                        Q(
                            incidents_filtered__status_history__status__name=(
                                NOTIFIED_CONTRACTOR_STATUS_NAME
                            )
                        )
                        | Q(incidents_filtered__avr_start_date__isnull=False)
                        | Q(incidents_filtered__rvr_start_date__isnull=False)
                    ),
                    distinct=True
                ),
            )
            .order_by('name', 'id')
        )

        for macroregion in base_qs:
            macroregion_sla = sla_map.get(macroregion.pk, {})
            for field in [
                'sla_avr_expired_count',
                'sla_avr_closed_on_time_count',
                'sla_avr_less_than_hour_count',
                'sla_avr_in_progress_count',
                'sla_rvr_expired_count',
                'sla_rvr_closed_on_time_count',
                'sla_rvr_less_than_hour_count',
                'sla_rvr_in_progress_count',
            ]:
                setattr(macroregion, field, macroregion_sla.get(field, 0))

        result = list(base_qs)

        cache.set(cache_key, result, STATISTIC_CACHE_TIMEOUT)

        return result

    def _get_incident_date_filter(
        self, start: Optional[date], end: Optional[date]
    ) -> Q:
        q = Q()

        if start:
            q &= Q(incident_date__date__gte=start)
        if end:
            q &= Q(incident_date__date__lte=end)

        return q

    def _get_macroregion_incident_filter(
        self, start: Optional[date], end: Optional[date]
    ) -> Q:
        q = Q()

        if start:
            q &= Q(
                regions__poles__incidents__incident_date__date__gte=start
            )
        if end:
            q &= Q(
                regions__poles__incidents__incident_date__date__lte=end
            )

        return q

    def _build_statistic_cache_key(
        self, start: Optional[date], end: Optional[date]
    ) -> str:
        start_key = start.isoformat() if start else 'none'
        end_key = end.isoformat() if end else 'none'
        return f'statistic_report:{start_key}:{end_key}'
