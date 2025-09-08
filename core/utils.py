import os
from typing import Optional

from django.utils import timezone

from .constants import (
    SUBFOLDER_DATE_FORMAT,
    SUBFOLDER_EMAIL_NAME,
)
from .exceptions import ConfigEnvError
from .loggers import LoggerFactory

app_logger = LoggerFactory(__name__).get_logger


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


def format_seconds(seconds: float) -> str:
    """Форматирует время в секундах в читаемый вид."""
    if seconds < 0.001:
        return f'{seconds * 1000:.0f} мс'
    elif seconds < 1:
        return f'{seconds * 1000:.1f} мс'
    elif seconds < 10:
        return f'{seconds:.2f} сек'
    elif seconds < 60:
        return f'{seconds:.1f} сек'
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f'{minutes} мин {remaining_seconds:.1f} сек'


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
