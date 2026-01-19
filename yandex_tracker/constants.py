import os
from datetime import timedelta

from django.utils import timezone

MAX_ATTACHMENT_SIZE_IN_YT = 50 * 1024 * 1024  # (max 50 MB в YandexTracker)

YT_ISSUES_DAYS_AGO_FILTER = 30

CURRENT_TZ = timezone.get_current_timezone()

MAX_PREVIEW_TEXT_LEN = 1024

NOTIFY_SPAM_DELAY = timedelta(seconds=60)  # Защита от спама автоответов

SEND_AUTO_EMAIL_ON_CLOSED_INCIDENT = (
    os.getenv('SEND_AUTO_EMAIL_ON_CLOSED_INCIDENT', 'False')
) == 'True'  # Автоответ, если оператор пишет в закрытую заявку


class IsExpiredSLA:
    unknown = '⬜️ Неизвестно'
    in_work = '🟦 В работе'
    one_hour = '🟨 Осталось менее часа'
    is_expired = '🟥 Просрочен'
    not_expired = '🟩 Закрыт вовремя'


class IsNewMsg:
    yes = '✔️ Да'
    no = '✖️ Нет'


MAX_MONITORING_DEVICES = 10


# Префиксы к подтипу инцидента:
INCIDENT_SUBTYPES_PREFIX = {
    'power_issue_types': 'АВАРИЯ ПО ПИТАНИЮ:',
}
