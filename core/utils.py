import multiprocessing
import os
from datetime import timedelta
from typing import Any, Callable, Optional

from django.utils import timezone
from django.http import HttpRequest
from django.utils.translation import ngettext

from .constants import (
    CONTROL_CHARS_RE,
    SUBFOLDER_DATE_FORMAT,
    SUBFOLDER_EMAIL_NAME,
    SUBFOLDER_MIME_EMAIL_NAME
)
from .exceptions import ConfigEnvError
from .loggers import default_logger


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
        return '0 секунд'

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days:
        parts.append(f'{days} {ngettext("день", "дней", days)}')
    if hours:
        parts.append(f'{hours} {ngettext("час", "часов", hours)}')
    if minutes:
        parts.append(f'{minutes} {ngettext("минута", "минут", minutes)}')

    if not parts and secs:
        parts.append(f'{secs} {ngettext("секунда", "секунд", secs)}')

    return ' '.join(parts)


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
                default_logger.critical(e)
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


def sanitize_http_filename(filename: str) -> str:
    """
    Убираем CR/LF и управляющие символы из имени файла
    ТОЛЬКО для использования в HTTP-заголовках
    """
    return CONTROL_CHARS_RE.sub(' ', filename).strip()


def get_param(request: HttpRequest, name: str) -> Optional[str]:
    if name in request.GET:
        return request.GET.get(name, '').strip()

    # Возвращаем если поиск был только с тукущей ссылки:
    referer: str = request.META.get('HTTP_REFERER', '')
    current_url = request.build_absolute_uri(request.path)
    is_same_page = referer.split('?')[0] == current_url

    if is_same_page:
        return request.COOKIES.get(name, '').strip()
