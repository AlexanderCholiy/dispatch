from datetime import timedelta

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

from incidents.annotations import annotate_sla_avr, annotate_sla_rvr
from incidents.constants import NOTIFIED_CONTRACTOR_STATUS_NAME
from incidents.models import Incident, IncidentStatusHistory
from ts.models import PoleContractorEmail, Region

from .constants import STATISTIC_CACHE_TIMEOUT
from .filters import IncidentReportFilter
from .pagination import IncidentReportPagination
from .serializers import IncidentReportSerializer, StatisticReportSerializer


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
    Возвращает статистику по регионам.

    Поля:

    - region_ru: название региона
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
    """
    serializer_class = StatisticReportSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None

    def get_queryset(self) -> QuerySet:
        cache_key = 'statistic_report_qs'
        cached_qs = cache.get(cache_key)

        if cached_qs is not None:
            return cached_qs

        incidents = Incident.objects.select_related('pole', 'incident_type')
        incidents = annotate_sla_avr(incidents)
        incidents = annotate_sla_rvr(incidents)

        region_sla_counts = (
            incidents.values('pole__region')
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

        sla_map = {item['pole__region']: item for item in region_sla_counts}

        dt = timedelta(hours=1)

        base_qs = (
            Region.objects
            .annotate(
                total_poles=Count('poles', distinct=True),
                total_closed_incidents=Count(
                    'poles__incidents',
                    filter=Q(
                        poles__incidents__code__isnull=False,
                        poles__incidents__is_incident_finish=True,
                        poles__incidents__incident_finish_date__isnull=False,
                        poles__incidents__incident_finish_date__gt=(
                            F('poles__incidents__incident_date') + dt
                        ),
                    ),
                    distinct=True
                ),
                total_open_incidents=Count(
                    'poles__incidents',
                    filter=Q(
                        poles__incidents__code__isnull=False,
                        poles__incidents__is_incident_finish=False,
                    ),
                    distinct=True
                ),
                active_contractor_incidents=Count(
                    'poles__incidents',
                    filter=Q(
                        poles__incidents__isnull=False,
                        poles__incidents__is_incident_finish=False
                    ) & (
                        Q(
                            poles__incidents__status_history__status__name=(
                                NOTIFIED_CONTRACTOR_STATUS_NAME
                            )
                        )
                        | Q(poles__incidents__avr_start_date__isnull=False)
                        | Q(poles__incidents__rvr_start_date__isnull=False)
                    ),
                    distinct=True
                ),
            )
            .order_by('region_ru', 'id')
        )

        for region in base_qs:
            region_sla = sla_map.get(region.pk, {})
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
                setattr(region, field, region_sla.get(field, 0))

        cache.set(cache_key, base_qs, STATISTIC_CACHE_TIMEOUT)

        return base_qs
