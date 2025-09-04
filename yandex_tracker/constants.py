from django.utils import timezone

INCIDENT_REGION_NOT_FOR_YT: list[str] = [
    'Moscow',
    'Moscow Region',
    'Leningrad Region',
    'Murmansk Region',
    'Kareliya Region',
    'Dagestan Region',
    'Ingushetia Region',
    'Kabardino-Balkariya Region',
    'Severnaya Osetiya-Alaniya Region',
    'Chechnya Region',
]

MAX_ATTACHMENT_SIZE_IN_YT = 50 * 1024 * 1024  # (max 50 MB в YandexTracker)

YT_ISSUES_DAYS_AGO_FILTER = 30

CURRENT_TZ = timezone.get_current_timezone()
MAX_PREVIEW_TEXT_LEN = 256


class IsExpiredSLA:
    unknown = '⬜️ Неизвестно'
    in_work = '🟦 В работе'
    one_hour = '🟨 Осталось менее часа'
    is_expired = '🟥 Просрочен'
    not_expired = '🟩 Закрыт вовремя'
