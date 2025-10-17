import os

from django.conf import settings

INCIDENTS_PER_PAGE = 32
INCIDENT_TYPES_PER_PAGE = 32
INCIDENT_STATUSES_PER_PAGE = 32
INCIDENT_CATEGORIES_PER_PAGE = 32

MAX_STATUS_COMMENT_LEN = 512
MAX_CODE_LEN = 32

INCIDENTS_DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'incidents')
INCIDENT_TYPES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'types.xlsx')
INCIDENT_STATUSES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'statuses.xlsx')
INCIDENT_CATEGORIES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'categories.xlsx')

# n-ое письмо после которого закрытая заявка, становится сново открытой:
MAX_EMAILS_ON_CLOSED_INCIDENTS = 2

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

DEFAULT_WAIT_ACCEPTANCE_STATUS_NAME = 'Ждем подтверждения'
DEFAULT_WAIT_ACCEPTANCE_STATUS_DESC = (
    'Ждем информацию об инциденте для его дальнейшей обработки.'
)

DEFAULT_GENERATION_STATUS_NAME = 'На генерации НБ'
DEFAULT_GENERATION_STATUS_DESC = 'Питание от генератора.'

DEFAULT_IN_WORK_STATUS_NAME = 'В работе'
DEFAULT_IN_WORK_STATUS_DESC = 'Заявка принята в работу.'

DEFAULT_NOTIFY_OP_IN_WORK_STATUS_NAME = 'Уведомляем оператора'
DEFAULT_NOTIFY_OP_IN_WORK_STATUS_DESC = (
    'Отправляем письмо заявителю о принятии инцидента в работу.')

DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME = 'Уведомили оператора'
DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_DESC = (
    'Отправили письмо заявителю о принятии инцидента в работу.')

DEFAULT_NOTIFY_OP_END_STATUS_NAME = 'Уведомляем о закрытии'
DEFAULT_NOTIFY_OP_END_STATUS_DESC = (
    'Отправляем письмо заявителю о закрытии работ.')

DEFAULT_NOTIFIED_OP_END_STATUS_NAME = 'Уведомили о закрытии'
DEFAULT_NOTIFIED_OP_END_STATUS_DESC = (
    'Отправили письмо заявителю о закрытии работ.')

DEFAULT_NOTIFY_AVR_STATUS_NAME = 'Передать подрядчику'
DEFAULT_NOTIFY_AVR_STATUS_DESC = 'Отправляем письмо с инцидентом подрядчику.'

DEFAULT_NOTIFIED_AVR_STATUS_NAME = 'Передано подрядчику'
DEFAULT_NOTIFIED_AVR_STATUS_DESC = 'Отправили письмо с инцидентом подрядчику.'

# В Трекере должно быть также:
DEFAULT_AVR_CATEGORY = 'АВР'
