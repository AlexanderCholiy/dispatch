import os

from django.conf import settings


INCIDENTS_PER_PAGE = 10

INCIDENTS_DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'incidents')
INCIDENT_TYPES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'types.xlsx')
INCIDENT_STATUSES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'statuses.xlsx')
