from django.db.models import QuerySet

from api.constants import (
    CACHE_INCIDENTS_FILE,
    CACHE_INCIDENTS_LAST_MONTH_FILE,
    CACHE_INCIDENTS_TTL,
)
from api.utils import get_first_day_prev_month, is_file_fresh
from api.views import IncidentReportViewSet


class IncidentsJsonBuilder:
    def __init__(self):
        self.view = IncidentReportViewSet()
        self._qs = None

    @property
    def qs(self) -> QuerySet:
        if self._qs is None:
            self._qs = self.view.get_queryset()
        return self._qs

    def update_incident_file(self):
        fresh, _ = is_file_fresh(CACHE_INCIDENTS_FILE, CACHE_INCIDENTS_TTL)
        if fresh:
            return

        self.view._generate_file(self.qs, CACHE_INCIDENTS_FILE)

    def update_incidents_last_month_file(self):
        fresh, _ = is_file_fresh(
            CACHE_INCIDENTS_LAST_MONTH_FILE, CACHE_INCIDENTS_TTL
        )
        if fresh:
            return

        first_day = get_first_day_prev_month()
        qs = self.qs.filter(incident_date__gte=first_day)

        self.view._generate_file(qs, CACHE_INCIDENTS_LAST_MONTH_FILE)
