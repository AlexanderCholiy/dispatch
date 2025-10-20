from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets, filters

from incidents.models import Incident, IncidentStatusHistory
from ts.models import PoleContractorEmail

from .filters import IncidentFilter
from .serializers import IncidentSerializer
from .pagination import IncidentPagination


class IncidentViewSet(viewsets.ReadOnlyModelViewSet):
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
        'responsible_user'
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

    serializer_class = IncidentSerializer
    permission_classes = (permissions.AllowAny,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = IncidentFilter
    pagination_class = IncidentPagination
    ordering_fields = ('incident_date', 'id')
    ordering = ('-incident_date', '-id')
