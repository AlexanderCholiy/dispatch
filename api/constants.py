import os
from datetime import timedelta
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.conf import settings

STATISTIC_CACHE_TIMEOUT = 20  # сек

ALL_CLOSED_INCIDENT_AGE_LIMIT = relativedelta(year=1)

API_DATE_FORMAT = '%Y-%m-%d'
API_DATETIME_FORMAT = '%Y-%m-%d %H:%M'

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

PERCENT_ACCURACY = 1

CACHE_ENERGY_DIR = Path(
    os.path.join(settings.MEDIA_ROOT, 'energy_cache')
)
os.makedirs(CACHE_ENERGY_DIR, exist_ok=True)

CACHE_ENERGY_CLAIMS_FILE = CACHE_ENERGY_DIR / 'claims_export.csv'
CACHE_ENERGY_APPEALS_FILE = CACHE_ENERGY_DIR / 'appeals_export.csv'
CACHE_ENERGY_TTL = timedelta(minutes=5)
ENERGY_DB_CHUNK_SIZE = 1_000

LOCK_KEY_CACHE_ENERGY_CLAIMS_FILE = f'lock__{CACHE_ENERGY_CLAIMS_FILE.name}'
LOCK_KEY_CACHE_ENERGY_APPEALS_FILE = f'lock__{CACHE_ENERGY_APPEALS_FILE.name}'

LOCK_ENERY_TIMEOUT_SEC = 600
LOCK_ENERGY_BLOCKING_TIMEOUT_SEC = 60
