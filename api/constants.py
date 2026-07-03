import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings

STATISTIC_CACHE_TIMEOUT = 20  # сек

API_DATE_FORMAT = '%Y-%m-%d'
API_DATETIME_FORMAT = '%Y-%m-%d %H:%M'

CACHE_INCIDENTS_DIR = Path(
    os.path.join(settings.MEDIA_ROOT, 'incidents_cache')
)

ARCHIVE_INCIDENTS_DIR = CACHE_INCIDENTS_DIR / 'archive'
ACTUAL_INCIDENTS_FILE = CACHE_INCIDENTS_DIR / 'actual_incidents.csv'

CACHE_INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)

ARCHIVE_INCIDENTS_TTL = timedelta(minutes=20)
ACTUAL_INCIDENTS_TTL = timedelta(minutes=10)

LOCK_KEY_ACTUAL_INCIDENTS = 'lock_incidents_csv_actual'
LOCK_KEY_ARCHIVE_INCIDENTS = 'lock_incidents_csv_archive'
LOCK_INCIDENTS_TIMEOUT_SEC = 300
LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC = 60

INCIDENTS_CSV_CHUNK = 1000
INCIDENTS_DB_CHUNK = 1000

PERCENT_ACCURACY = 1

CACHE_ENERGY_DIR = Path(
    os.path.join(settings.MEDIA_ROOT, 'energy_cache')
)
os.makedirs(CACHE_ENERGY_DIR, exist_ok=True)

CACHE_ENERGY_CLAIMS_FILE = CACHE_ENERGY_DIR / 'claims_export.csv'
CACHE_ENERGY_APPEALS_FILE = CACHE_ENERGY_DIR / 'appeals_export.csv'
CACHE_ENERGY_TTL = timedelta(minutes=30)
ENERGY_DB_CHUNK_SIZE = 1_000

LOCK_KEY_CACHE_ENERGY_CLAIMS_FILE = f'lock__{CACHE_ENERGY_CLAIMS_FILE.name}'
LOCK_KEY_CACHE_ENERGY_APPEALS_FILE = f'lock__{CACHE_ENERGY_APPEALS_FILE.name}'

LOCK_ENERY_TIMEOUT_SEC = 300
LOCK_ENERGY_BLOCKING_TIMEOUT_SEC = 60
