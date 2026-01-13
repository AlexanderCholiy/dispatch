from datetime import date
from typing import Optional

from django.core.cache import cache
from django.db.models import (
    Count,
    F,
    Prefetch,
    Q,
    QuerySet,
)
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

from .constants import CLOSED_INCIDENT_CHECK_TIMER, STATISTIC_CACHE_TIMEOUT
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
    - open_incidents_with_power_issue: количество открытых инцидентов, у
    которых выявлена проблема с питанием на опоре с проверкой по мониторингу
    - closed_incidents_with_power_issue: количество закрытых инцидентов, у
    которых выявлена проблема с питанием на опоре с проверкой по мониторингу

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

        incidents = self.filter_queryset(
            Incident.objects
            .select_related('pole', 'incident_type')
            .filter(incident_date_filter)
        )

        base_incidents = annotate_sla_avr(incidents)
        base_incidents = annotate_sla_rvr(base_incidents)

        incident_stats = (
            base_incidents
            .values('pole__region__macroregion')
            .annotate(
                total_closed_incidents=Count(
                    'id',
                    filter=Q(
                        is_incident_finish=True,
                        code__isnull=False,
                        incident_finish_date__isnull=False,
                        incident_finish_date__gt=(
                            F('incident_date') + CLOSED_INCIDENT_CHECK_TIMER
                        ),
                    )
                ),
                total_open_incidents=Count(
                    'id',
                    filter=Q(
                        is_incident_finish=False,
                        code__isnull=False,
                    )
                ),
                active_contractor_incidents=Count(
                    'id',
                    distinct=True,
                    filter=(
                        Q(
                            is_incident_finish=False,
                            code__isnull=False,
                        )
                        & (
                            Q(
                                status_history__status__name=(
                                    NOTIFIED_CONTRACTOR_STATUS_NAME
                                )
                            )
                            | Q(avr_start_date__isnull=False)
                            | Q(rvr_start_date__isnull=False)
                        )
                    )
                ),
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

        # Отдельно считаем открытые и закрытые с проблемой питания
        power_base = base_incidents.filter(
            code__isnull=False
        ).filter(
            Q(is_incident_finish=False)
            | Q(
                is_incident_finish=True,
                incident_finish_date__isnull=False,
                incident_finish_date__gt=(
                    F('incident_date') + CLOSED_INCIDENT_CHECK_TIMER
                )
            )
        )
        power_incidents = annotate_is_power_issue(power_base).filter(
            is_power_issue=True
        )

        open_power_map = {
            item['pole__region__macroregion']: item['c']
            for item in (
                power_incidents
                .filter(is_incident_finish=False)
                .values('pole__region__macroregion')
                .annotate(c=Count('id'))
            )
        }

        closed_power_map = {
            item['pole__region__macroregion']: item['c']
            for item in (
                power_incidents
                .filter(is_incident_finish=True)
                .values('pole__region__macroregion')
                .annotate(c=Count('id'))
            )
        }

        stats_map = {
            item['pole__region__macroregion']: item for item in incident_stats
        }

        macroregions = list(MacroRegion.objects.order_by('name', 'id'))

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
