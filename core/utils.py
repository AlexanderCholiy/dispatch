import multiprocessing
import os
from datetime import timedelta
from typing import Any, Callable, Optional

from django.utils import timezone

from .constants import (
    SUBFOLDER_DATE_FORMAT,
    SUBFOLDER_EMAIL_NAME,
    SUBFOLDER_MIME_EMAIL_NAME,
)
from .exceptions import ConfigEnvError
from .loggers import LoggerFactory

app_logger = LoggerFactory(__name__).get_logger()


def attachment_upload_to(instance, filename: str):
    """
    Формируем путь вида:
    attachments/YYYY-MM-DD/filename.ext
    (относительно MEDIA_ROOT)
    """
    if (
        hasattr(instance, 'email_msg')
        and instance.email_msg
        and instance.email_msg.email_date
    ):
        date_str = instance.email_msg.email_date.strftime(
            SUBFOLDER_DATE_FORMAT
        )
    else:
        date_str = timezone.now().strftime(SUBFOLDER_DATE_FORMAT)

    return os.path.join(SUBFOLDER_EMAIL_NAME, date_str, filename)


def email_mime_upload_to(instance, filename: str):
    """
    Формируем путь вида:
    email_mime/YYYY-MM-DD/filename.eml
    """
    if (
        hasattr(instance, 'email_msg')
        and instance.email_msg
        and instance.email_msg.email_date
    ):
        date_str = instance.email_msg.email_date.strftime(
            SUBFOLDER_DATE_FORMAT
        )
    else:
        date_str = timezone.now().strftime(SUBFOLDER_DATE_FORMAT)

    return os.path.join(SUBFOLDER_MIME_EMAIL_NAME, date_str, filename)


def format_seconds(seconds: float) -> str:
    """Форматирует время в секундах в читаемый вид."""
    if seconds < 0.001:
        return f'{seconds * 1000:.0f} мс'
    elif seconds < 1:
        return f'{seconds * 1000:.1f} мс'
    elif seconds < 60:
        if seconds < 10:
            return f'{seconds:.2f} сек'
        else:
            return f'{seconds:.1f} сек'
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f'{minutes} мин {remaining_seconds:.1f} сек'
    elif seconds < 86400:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        remaining_seconds = seconds % 60
        return f'{hours} ч {remaining_minutes} мин {remaining_seconds:.0f} сек'
    else:
        days = int(seconds // 86400)
        remaining_hours = int((seconds % 86400) // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        return f'{days} дн {remaining_hours} ч {remaining_minutes} мин'


def timedelta_to_human_time(time_delta: timedelta) -> str:
    seconds = int(time_delta.total_seconds())
    if seconds <= 0:
        raise ValueError('Значение должно быть > 0')

    time_units = {
        'день': 86400,
        'час': 3600,
        'минута': 60,
        'секунда': 1,
    }

    parts = []
    remaining_seconds = seconds

    for unit_name, unit_seconds in time_units.items():
        if remaining_seconds >= unit_seconds:
            unit_value = remaining_seconds // unit_seconds
            remaining_seconds %= unit_seconds

            if unit_name == 'день':
                if unit_value % 10 == 1 and unit_value % 100 != 11:
                    unit_name_formatted = 'день'
                elif (
                    2 <= unit_value % 10 <= 4
                    and (unit_value % 100 < 10 or unit_value % 100 >= 20)
                ):
                    unit_name_formatted = 'дня'
                else:
                    unit_name_formatted = 'дней'
            elif unit_name == 'час':
                if unit_value % 10 == 1 and unit_value % 100 != 11:
                    unit_name_formatted = 'час'
                elif (
                    2 <= unit_value % 10 <= 4
                    and (unit_value % 100 < 10 or unit_value % 100 >= 20)
                ):
                    unit_name_formatted = 'часа'
                else:
                    unit_name_formatted = 'часов'
            elif unit_name == 'минута':
                if unit_value % 10 == 1 and unit_value % 100 != 11:
                    unit_name_formatted = 'минута'
                elif (
                    2 <= unit_value % 10 <= 4
                    and (unit_value % 100 < 10 or unit_value % 100 >= 20)
                ):
                    unit_name_formatted = 'минуты'
                else:
                    unit_name_formatted = 'минут'
            elif unit_name == 'секунда':
                if unit_value % 10 == 1 and unit_value % 100 != 11:
                    unit_name_formatted = 'секунда'
                elif (
                    2 <= unit_value % 10 <= 4
                    and (unit_value % 100 < 10 or unit_value % 100 >= 20)
                ):
                    unit_name_formatted = 'секунды'
                else:
                    unit_name_formatted = 'секунд'

            parts.append(f'{unit_value} {unit_name_formatted}')

    return ', '.join(parts)


class Config:
    @staticmethod
    def validate_env_variables(env_vars: dict[str, Optional[str]]):
        """
        Проверка переменных окружения.
        Args:
            env_vars (dict): Словарь с переменными окружения.

        Example:
            ```python
            env_vars {
                'WEB_SECRET_KEY': 'my_secret_key',
                'WEB_BOT_EMAIL_LOGIN': 'bot@email.com',
                'WEB_BOT_EMAIL_PSWD': None,
                'EMAIL_SERVER': 'microsoft@outlook.com',
            }  # raise ConfigEnvError
            ```
        """
        missing_vars = [
            var_name
            for var_name, var_value in env_vars.items()
            if var_value is None
        ]

        if missing_vars:
            try:
                raise ConfigEnvError(missing_vars)
            except ConfigEnvError as e:
                app_logger.critical(e)
                raise


def run_with_timeout_process(
    func: Callable, func_timeout: int, *args, **kwargs
) -> Any:
    """Запуск функции в отдельном процессе с ограничением по времени."""
    with multiprocessing.Manager() as manager:
        return_dict = manager.dict()

        def wrapper(return_dict):
            try:
                result = func(*args, **kwargs)
                return_dict['result'] = result
            except Exception as e:
                return_dict['exception'] = e

        p = multiprocessing.Process(target=wrapper, args=(return_dict,))
        p.start()
        p.join(func_timeout)

        if p.is_alive():
            p.terminate()
            p.join()
            raise TimeoutError(
                f'Время выполнения функции {func.__name__} превысило '
                f'{func_timeout} секунд'
            )

        if 'exception' in return_dict:
            raise return_dict['exception']

        return return_dict.get('result')
