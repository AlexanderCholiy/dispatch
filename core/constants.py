import os
from http import HTTPStatus
from logging import DEBUG, INFO

from django.conf import settings

from .exceptions import (
    ApiBadRequest,
    ApiForbidden,
    ApiMethodNotAllowed,
    ApiNotFound,
    ApiUnauthorizedErr,
)

BASE_DIR = settings.BASE_DIR
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DEBUG_MODE: bool = settings.DEBUG

DEFAULT_LOG_FILE = os.path.join(LOG_DIR, 'log.log')
DEFAULT_ROTATING_LOG_FILE = os.path.join(LOG_DIR, 'default', 'rt_log.log')
DEFAULT_LOG_MODE = 4 if DEBUG_MODE else 1
DEFAULT_LOG_LEVEL = DEBUG if DEBUG_MODE else INFO

EMAIL_LOG_ROTATING_FILE = os.path.join(LOG_DIR, 'emails', 'emails.log')
TS_LOG_ROTATING_FILE = os.path.join(LOG_DIR, 'ts', 'ts.log')
YANDEX_TRACKER_ROTATING_FILE = os.path.join(
    LOG_DIR, 'yandex_tracker', 'yandex_tracker.log')
INCIDENTS_LOG_ROTATING_FILE = os.path.join(
    LOG_DIR, 'incidents', 'incidents.log')
TG_NOTIFICATIONS_ROTATING_FILE = os.path.join(
    LOG_DIR, 'telegram', 'telegram.log')
YANDEX_TRACKER_AUTO_EMAILS_ROTATING_FILE = os.path.join(
    LOG_DIR, 'yandex_tracker', 'yandex_tracker_auto_emails.log')

MAX_FILE_URL_LEN = 512
MAX_ST_DESCRIPTION = 256
MAX_LG_DESCRIPTION = 1024
MAX_EMAIL_ID_LEN = 256

SUBFOLDER_DATE_FORMAT = '%Y-%m-%d'
SUBFOLDER_EMAIL_NAME = 'emails_attachments'
# Модель Attachment настроена на папку settings.MEDIA_ROOT:
INCIDENT_DIR = os.path.join(settings.MEDIA_ROOT, SUBFOLDER_EMAIL_NAME)
EMPTY_VALUE = 'Не задано'

API_STATUS_EXCEPTIONS = {
    HTTPStatus.UNAUTHORIZED: ApiUnauthorizedErr,
    HTTPStatus.FORBIDDEN: ApiForbidden,
    HTTPStatus.NOT_FOUND: ApiNotFound,
    HTTPStatus.BAD_REQUEST: ApiBadRequest,
    HTTPStatus.METHOD_NOT_ALLOWED: ApiMethodNotAllowed,
}

MIN_WAIT_SEC_WITH_CRITICAL_EXC = 60
