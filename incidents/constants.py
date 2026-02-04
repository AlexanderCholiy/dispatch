import os
from datetime import timedelta

from django.conf import settings

MAX_INCIDENTS_INFO_CACHE_SEC = 3600

INCIDENTS_PER_PAGE = 50
PAGE_SIZE_INCIDENTS_CHOICES = [25, INCIDENTS_PER_PAGE, 100, 200, 500]

INCIDENT_TYPES_PER_PAGE = 32
INCIDENT_STATUSES_PER_PAGE = 32
INCIDENT_CATEGORIES_PER_PAGE = 32
INCIDENT_SUBTYPES_PER_PAGE = 32

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

END_STATUS_NAME = 'Закрыт'
END_STATUS_DESC = (
    'Инцидент полностью обработан и закрыт, никаких дальнейших действий не '
    'требуется.'
)

ERR_STATUS_NAME = 'Ошибка'
ERR_STATUS_DESC = (
    'Обнаружена ошибка при обработке инцидента или некорректные данные.'
)

WAIT_ACCEPTANCE_STATUS_NAME = 'Ждем подтверждения'
WAIT_ACCEPTANCE_STATUS_DESC = (
    'Ждем информацию об инциденте для его дальнейшей обработки.'
)

GENERATION_STATUS_NAME = 'На генерации НБ'
GENERATION_STATUS_DESC = 'Питание от генератора.'

IN_WORK_STATUS_NAME = 'В работе'
IN_WORK_STATUS_DESC = 'Заявка принята в работу.'

NOTIFY_OP_IN_WORK_STATUS_NAME = 'Уведомляем оператора'
NOTIFY_OP_IN_WORK_STATUS_DESC = (
    'Отправляем письмо заявителю о принятии инцидента в работу.'
)

NOTIFIED_OP_IN_WORK_STATUS_NAME = 'Уведомили оператора'
NOTIFIED_OP_IN_WORK_STATUS_DESC = (
    'Отправили письмо заявителю о принятии инцидента в работу.'
)

NOTIFY_OP_END_STATUS_NAME = 'Уведомляем о закрытии'
NOTIFY_OP_END_STATUS_DESC = (
    'Отправляем письмо заявителю о закрытии работ.'
)

NOTIFIED_OP_END_STATUS_NAME = 'Уведомили о закрытии'
NOTIFIED_OP_END_STATUS_DESC = (
    'Отправили письмо заявителю о закрытии работ.'
)

NOTIFY_CONTRACTOR_STATUS_NAME = 'Передать подрядчику'
NOTIFY_CONTRACTOR_STATUS_DESC = (
    'Отправляем письмо с инцидентом подрядчику.'
)

NOTIFIED_CONTRACTOR_STATUS_NAME = 'Передано подрядчику'
NOTIFIED_CONTRACTOR_STATUS_DESC = (
    'Отправили письмо с инцидентом подрядчику.'
)

# В Трекере должно быть также, также есть связь в истории статусов:
AVR_CATEGORY = 'АВР'
RVR_CATEGORY = 'РВР'
DGU_CATEGORY = 'ДГУ'

# Дедлайн SLA РВР:
RVR_SLA_DEADLINE_IN_HOURS = 72

# Дедлайн SLA ДГУ:
DGU_SLA_IN_PROGRESS_DEADLINE_IN_HOURS = 12
DGU_SLA_WAITING_DEADLINE_IN_HOURS = 24 * 15

# Ограничение для закрытия SLA в будущем:
MAX_FUTURE_END_DELTA = timedelta(minutes=5)

# Все основные типы инцидентов:
INCIDENT_POWER_SUPLY_RF_TYPE = 'Авария по питанию РФ'
INCIDENT_POWER_SUPLY_MSK_TYPE = 'Авария по питанию для МСК'
INCIDENT_POWER_SUPLY_NB_EMPLOYEE_TYPE = 'Авария по питанию от сотрудника НБ'
INCIDENT_AMS_STRUCTURE_TYPE = 'Инцидент по конструктиву / территорией АМС'
INCIDENT_GOVERMENT_REQUEST_TYPE = 'Инцидент / запрос гос. органов'
INCIDENT_VOLS_TYPE = 'Авария ВОЛС'
INCIDENT_DESTRUCTION_OBJECT_TYPE = 'Угроза гибели / гибель объекта'
INCIDENT_ACCESS_TO_OBJECT_TYPE = 'Запрос на организацию доступа к объекту'

# По данным типам инцидетов, определяются те у которых нет питания:
POWER_ISSUE_TYPES = (
    INCIDENT_POWER_SUPLY_RF_TYPE,
    INCIDENT_POWER_SUPLY_MSK_TYPE,
    INCIDENT_POWER_SUPLY_NB_EMPLOYEE_TYPE,
)
