import os
from logging import DEBUG, INFO

from django.conf import settings

BASE_DIR = settings.BASE_DIR
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DEBUG_MODE: bool = settings.DEBUG

DEFAULT_LOG_FILE = os.path.join(LOG_DIR, 'log.log')
DEFAULT_ROTATING_LOG_FILE = os.path.join(LOG_DIR, 'rotating_log.log')
DEFAULT_LOG_MODE = 4 if DEBUG_MODE else 1
DEFAULT_LOG_LEVEL = DEBUG if DEBUG_MODE else INFO

EMAIL_LOG_ROTATING_FILE = os.path.join(LOG_DIR, 'emails.log')
TS_LOG_ROTATING_FILE = os.path.join(LOG_DIR, 'ts.log')

MAX_FILE_NAME_LEN = 256
MAX_FILE_URL_LEN = 512
MAX_ST_DESCRIPTION = 256
MAX_LG_DESCRIPTION = 1024
MAX_EMAIL_ID_LEN = 256

EMAIL_ATTACHMENT_FOLDER_NAME = 'email_attachments'
SUBFOLDER_DATE_FORMAT = '%Y-%m-%d'
INCIDENT_DIR = os.path.join(
    BASE_DIR, settings.MEDIA_ROOT, EMAIL_ATTACHMENT_FOLDER_NAME
)
EMPTY_VALUE = 'Не задано'
