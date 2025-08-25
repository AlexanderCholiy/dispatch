import os

from django.conf import settings


INCIDENTS_PER_PAGE = 10

INCIDENTS_DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'incidents')
INCIDENT_TYPES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'types.xlsx')
INCIDENT_STATUSES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'statuses.xlsx')

DEFAULT_STATUS_NAME = 'Новый'
DEFAULT_STATUS_DESC = (
    'Инцидент только что создан и ещё не был принят в работу диспетчером'
)
