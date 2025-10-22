from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.request import Request

from incidents.models import Incident, IncidentStatusHistory
from ts.models import PoleContractorEmail

from .filters import IncidentReportFilter
from .pagination import IncidentReportPagination
from .serializers import IncidentReportSerializer


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
