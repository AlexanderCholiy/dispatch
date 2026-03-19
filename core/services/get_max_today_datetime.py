from django.utils import timezone

from core.constants import DATETIME_LOCAL_FORMAT


def get_max_today_datetime():
    """
    Возвращает строку текущей даты с максимальным временем (23:59)
    в формате, подходящем для атрибута 'max' в datetime-local.
    """
    return timezone.now().replace(
        hour=23,
        minute=59,
        second=0,
        microsecond=0
    ).strftime(DATETIME_LOCAL_FORMAT)
