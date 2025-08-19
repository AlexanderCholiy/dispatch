import os
from logging import DEBUG, INFO

from django.conf import settings

BASE_DIR = settings.BASE_DIR
LOG_DIR = os.path.join(BASE_DIR, 'logs')

DEFAULT_LOG_FILE = os.path.join(LOG_DIR, 'log.log')
DEFAULT_ROTATING_LOG_FILE = os.path.join(LOG_DIR, 'rotating_log.log')
DEFAULT_LOG_MODE = 4 if settings.DEBUG else 1
DEFAULT_LOG_LEVEL = DEBUG if settings.DEBUG else INFO

EMAIL_ROTATING_FILE = os.path.join(LOG_DIR, 'emails.log')
