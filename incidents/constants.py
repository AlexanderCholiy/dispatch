import os
from datetime import timedelta

from django.conf import settings

MAX_INCIDENTS_INFO_CACHE_SEC = 3600

INCIDENTS_PER_PAGE = 25
PAGE_SIZE_INCIDENTS_CHOICES = [15, INCIDENTS_PER_PAGE, 50, 100, 200, 500]

INCIDENT_TYPES_PER_PAGE = 32
INCIDENT_STATUSES_PER_PAGE = 32
INCIDENT_CATEGORIES_PER_PAGE = 32
INCIDENT_SUBTYPES_PER_PAGE = 32
INCIDENT_CHANGE_LOG_PER_PAGE = 100  # то же и на странице карточки инцидента

MAX_STATUS_COMMENT_LEN = 512
MAX_CODE_LEN = 32

INCIDENTS_DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'incidents')
INCIDENT_TYPES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'types.xlsx')
INCIDENT_STATUSES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'statuses.xlsx')
INCIDENT_CATEGORIES_FILE = os.path.join(INCIDENTS_DATA_DIR, 'categories.xlsx')

# n-ое письмо после которого закрытая заявка, становится сново открытой:
MAX_EMAILS_ON_CLOSED_INCIDENTS = 2
INCIDENT_CODE_PREFIX = 'NT'
INCIDENT_YT_CODE_PREFIX = 'AVRSERVICE'

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

REQUEST_FOR_ADD_DATA_STATUS_NAME = 'Запрос доп. данных'
REQUEST_FOR_ADD_DATA_STATUS_DESC = (
    'Запрос дополнительной информации от заявителя, по инциденту'
)

FINISHED_STATUS_NAMES = [END_STATUS_NAME, GENERATION_STATUS_NAME]

# В Трекере должно быть также, также есть связь в истории статусов:
AVR_CATEGORY = 'АВР'
RVR_CATEGORY = 'РВР'
DGU_CATEGORY = 'ДГУ'
EKS_CATEGORY = 'ЭКС'

TOTAL_CATEGORIES = [AVR_CATEGORY, RVR_CATEGORY, DGU_CATEGORY, EKS_CATEGORY]

# Дедлайн SLA РВР:
RVR_SLA_DEADLINE_IN_HOURS = 72

# Дедлайн SLA ДГУ:
DGU_SLA_IN_PROGRESS_DEADLINE_IN_HOURS = 12
DGU_SLA_WAITING_DEADLINE_IN_HOURS = 24 * 15

# Дедлайн SLA ЭКС:
EKS_SLA_IN_PROGRESS_DEADLINE_IN_HOURS = 12
EKS_SLA_WAITING_DEADLINE_IN_HOURS = 24 * 15

# Дедлайн диспетчеров:
DISPATCH_SLA_DEADLINE = timedelta(minutes=10)

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

STATUS_TRANSITIONS = {
    DEFAULT_STATUS_NAME: [
        IN_WORK_STATUS_NAME,
        END_STATUS_NAME,
        WAIT_ACCEPTANCE_STATUS_NAME,
        REQUEST_FOR_ADD_DATA_STATUS_NAME,
    ],
    IN_WORK_STATUS_NAME: [
        NOTIFIED_OP_IN_WORK_STATUS_NAME,
        END_STATUS_NAME,
        GENERATION_STATUS_NAME,
        WAIT_ACCEPTANCE_STATUS_NAME,
        NOTIFIED_OP_END_STATUS_NAME,
        REQUEST_FOR_ADD_DATA_STATUS_NAME,
    ],
    REQUEST_FOR_ADD_DATA_STATUS_NAME: [
        IN_WORK_STATUS_NAME,
        END_STATUS_NAME,
        GENERATION_STATUS_NAME,
        WAIT_ACCEPTANCE_STATUS_NAME,
        NOTIFIED_OP_END_STATUS_NAME,
    ],
    NOTIFIED_OP_IN_WORK_STATUS_NAME: [
        NOTIFIED_CONTRACTOR_STATUS_NAME,
        NOTIFIED_OP_END_STATUS_NAME,
        GENERATION_STATUS_NAME,
        WAIT_ACCEPTANCE_STATUS_NAME,
    ],
    NOTIFIED_CONTRACTOR_STATUS_NAME: [
        GENERATION_STATUS_NAME,
        END_STATUS_NAME,
        WAIT_ACCEPTANCE_STATUS_NAME,
        NOTIFIED_OP_END_STATUS_NAME,

    ],
    NOTIFIED_OP_END_STATUS_NAME: [
        GENERATION_STATUS_NAME,
        END_STATUS_NAME,
        WAIT_ACCEPTANCE_STATUS_NAME,
    ],
    END_STATUS_NAME: [IN_WORK_STATUS_NAME],
    GENERATION_STATUS_NAME: [
        NOTIFIED_OP_END_STATUS_NAME,
        END_STATUS_NAME,
        WAIT_ACCEPTANCE_STATUS_NAME,
    ],
    WAIT_ACCEPTANCE_STATUS_NAME: [
        NOTIFIED_OP_IN_WORK_STATUS_NAME,
        NOTIFIED_CONTRACTOR_STATUS_NAME,
        NOTIFIED_OP_END_STATUS_NAME,
        END_STATUS_NAME,
        GENERATION_STATUS_NAME,
    ],
    ERR_STATUS_NAME: [
        IN_WORK_STATUS_NAME,
    ],
    # Для этих статусов значение меняется автоматически:
    NOTIFY_OP_IN_WORK_STATUS_NAME: [ERR_STATUS_NAME,],
    NOTIFY_CONTRACTOR_STATUS_NAME: [ERR_STATUS_NAME,],
    NOTIFY_OP_END_STATUS_NAME: [ERR_STATUS_NAME,],
}

RUSSIA_EMPTY_MACRO_ID = 0

AUTO_REPLY_MAX_AGE_TTL = timedelta(hours=1)

MAX_COMMENT_TEXT_LEN = 2048

INCIDENT_COMMENTS_PER_PAGE = 25

INCIDENT_COMMENT_MAX_PREVIEW_LEN = 32

MAX_INCIDENT_COMMENTS_PER_PAGE = 500

DEFAULT_IS_YT_TRACKER_CONTROLLED = False

AUTO_CLOSE_CACHE_KEY_PREFIX = 'auto_close_task:'

AUTO_CLOSE_TTL = timedelta(hours=12)

# Необходимая добавка для SLA, т.к. секунды frontend не передает:
SLA_BUFFER = timedelta(minutes=1)

CLEANUP_OLD_INCIDENT_CHANGE_LOG_TTL = timedelta(days=365)

INCIDENT_CHANGE_LOG_BATCH_SIZE = 1000

INCIDENT_BATCH_SIZE = 1000

MAX_INCIDENT_LINKS = 25

STATUSES_FOR_AUTOCLOSE = [
    NOTIFIED_OP_END_STATUS_NAME,
    REQUEST_FOR_ADD_DATA_STATUS_NAME,
]

CACHE_SIMILAR_INCIDENTS_PREFIX = 'similar_incidents'
CACHE_SIMILAR_INCIDENTS_TTL = 600

# Максимальное окно поиска в секундах (3 недели) схожих инцидентов:
MAX_SIMILAR_INCIDENTS_WINDOW_TTL = 7 * 3 * 24 * 3600
MAX_SIMILAR_INCIDENTS_THRESHOLD = 0.5
MAX_SIMILAR_INCIDENTS_CANDIDATES = 1000


class SimilarFactor:
    """Константы весов для расчета схожести инцидентов."""

    pole = 0.2
    bs = 0.4
    incident_type = 0.05
    incident_sub_type = 0.1
    categories = 0.1
    incident_email_subject = 0.13
    incident_email_from = 0.02
