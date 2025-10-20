from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets

from incidents.models import Incident, IncidentStatusHistory
from ts.models import PoleContractorEmail

from .filters import IncidentFilter
from .serializers import IncidentSerializer


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
    ).order_by('-incident_date', '-id')

    serializer_class = IncidentSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IncidentFilter
