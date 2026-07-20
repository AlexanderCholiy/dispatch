import os
from pathlib import Path
from typing import TypedDict

from django.db import models

from core.constants import TMP_DATA_DIR

BASE_URL = 'https://max.ru'

MAX_TOKEN = os.getenv('MAX_TOKEN')
MAX_CHAT_ID = int(os.getenv('MAX_CHAT_ID', 0))

MAX_CERT_DIR = Path(TMP_DATA_DIR) / 'max' / 'cert'

MAX_MSG_TTL = 900
MAX_INCIDENT_SPAM_KEY_PREFIX = 'incident:'


class MaxNotificationStatus(models.TextChoices):
    """Статусы отправки уведомления в MAX."""
    PENDING = ('pending', 'Отправляется')
    SENT = ('sent', 'Отправлено')
    ERROR = ('error', 'Ошибка')


class MaxNotificationData(TypedDict):
    timestamp: str
    status: str
