import os

from django.conf import settings

INCIDENTS_PER_PAGE = 32
INCIDENT_TYPES_PER_PAGE = 32
INCIDENT_STATUSES_PER_PAGE = 32

MAX_STATUS_COMMENT_LEN = 512

INCIDENTS_DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'incidents')
INCIDENT_TYPES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'types.xlsx')
INCIDENT_STATUSES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'statuses.xlsx')

DEFAULT_STATUS_NAME = 'Новый'
DEFAULT_STATUS_DESC = (
    'Инцидент только что создан и ещё не был принят в работу диспетчером.'
)

DEFAULT_END_STATUS_NAME = 'Закрыт'
DEFAULT_END_STATUS_DESC = (
    'Инцидент полностью обработан и закрыт, никаких дальнейших действий не '
    'требуется.'
)

DEFAULT_ERR_STATUS_NAME = 'Ошибка'
DEFAULT_ERR_STATUS_DESC = (
    'Обнаружена ошибка при обработке инцидента или некорректные данные.'
)
