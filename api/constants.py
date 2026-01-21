from datetime import timedelta

from django.db.models import F, Q

STATISTIC_CACHE_TIMEOUT = 20  # сек

CLOSED_INCIDENTS_CHECK_TIMER = timedelta(hours=1)

BASE_INCIDENT_VALID_FILTER = Q(code__isnull=False)

CLOSED_INCIDENTS_VALID_FILTER = BASE_INCIDENT_VALID_FILTER & Q(
    is_incident_finish=True,
    incident_finish_date__isnull=False,
    # Убераем инциденты, которые закрыли сразу:
    incident_finish_date__gt=F('incident_date') + CLOSED_INCIDENTS_CHECK_TIMER
)

OPEN_INCIDENTS_VALID_FILTER = BASE_INCIDENT_VALID_FILTER & Q(
    is_incident_finish=False
)

TOTAL_VALID_INCIDENTS_FILTER = (
    CLOSED_INCIDENTS_VALID_FILTER | OPEN_INCIDENTS_VALID_FILTER
)

API_DATE_FORMAT = '%Y-%m-%d'
