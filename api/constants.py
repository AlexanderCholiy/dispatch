import os
from datetime import timedelta
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Q

STATISTIC_CACHE_TIMEOUT = 20  # сек

# CLOSED_INCIDENTS_CHECK_TIMER = timedelta(hours=1)

BASE_INCIDENT_VALID_FILTER = Q(code__isnull=False)

CLOSED_INCIDENTS_VALID_FILTER = BASE_INCIDENT_VALID_FILTER & Q(
    is_incident_finish=True,
    incident_finish_date__isnull=False,
    # Убераем инциденты, которые закрыли сразу:
    # incident_finish_date__gt=(
    #     F('incident_date') + CLOSED_INCIDENTS_CHECK_TIMER
    # )
)

ALL_CLOSED_INCIDENT_AGE_LIMIT = relativedelta(year=1)

OPEN_INCIDENTS_VALID_FILTER = BASE_INCIDENT_VALID_FILTER & Q(
    is_incident_finish=False
)

TOTAL_VALID_INCIDENTS_FILTER = (
    CLOSED_INCIDENTS_VALID_FILTER | OPEN_INCIDENTS_VALID_FILTER
)

API_DATE_FORMAT = '%Y-%m-%d'

CACHE_INCIDENTS_DIR = Path(
    os.path.join(settings.MEDIA_ROOT, 'incidents_cache')
)
os.makedirs(CACHE_INCIDENTS_DIR, exist_ok=True)

CACHE_INCIDENTS_FILE = CACHE_INCIDENTS_DIR / 'incidents_export.json'
CACHE_INCIDENTS_LAST_MONTH_FILE = (
    CACHE_INCIDENTS_DIR / 'incidents_last_month_export.json'
)
CACHE_INCIDENTS_TTL = timedelta(minutes=5)
JSON_EXPORT_CHUNK_SIZE = 10_000
INCIDENT_DB_CHUNK_SIZE = 1_000

LOCK_KEY_CACHE_INCIDENTS_FILE = f'lock__{CACHE_INCIDENTS_FILE.name}'
LOCK_KEY_CACHE_INCIDENTS_LAST_MONTH_FILE = (
    f'lock__{CACHE_INCIDENTS_LAST_MONTH_FILE.name}'
)
LOCK_INCIDENTS_TIMEOUT_SEC = 600
LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC = 60
