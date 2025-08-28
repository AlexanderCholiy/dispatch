import os
import time

from django.core.management.base import BaseCommand

from core.constants import (
    EMAIL_LOG_ROTATING_FILE,
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
)
from core.loggers import LoggerFactory
from core.utils import Config
from emails.email_parser import EmailParser
from yandex_tracker.utils import YandexTrackerManager

email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'

    def handle(self, *args, **kwargs):
        yt_manager_config = {
            'YT_CLIENT_ID': os.getenv('YT_CLIENT_ID'),
            'YT_CLIENT_SECRET': os.getenv('YT_CLIENT_SECRET'),
            'YT_ACCESS_TOKEN': os.getenv('YT_ACCESS_TOKEN'),
            'YT_REFRESH_TOKEN': os.getenv('YT_REFRESH_TOKEN'),
            'YT_ORGANIZATION_ID': os.getenv('YT_ORGANIZATION_ID'),
            'YT_QUEUE': os.getenv('YT_QUEUE'),
            'YT_DATABASE_GLOBAL_FIELD_ID': os.getenv('YT_DATABASE_GLOBAL_FIELD_ID'),  # noqa: E501
            'YT_POLE_NUMBER_GLOBAL_FIELD_ID': os.getenv('YT_POLE_NUMBER_GLOBAL_FIELD_ID'),  # noqa: E501
            'YT_BASE_STATION_GLOBAL_FIELD_ID': os.getenv('YT_BASE_STATION_GLOBAL_FIELD_ID'),  # noqa: E501
            'YT_EMAIL_DATETIME_GLOBAL_FIELD_ID': os.getenv('YT_EMAIL_DATETIME_GLOBAL_FIELD_ID'),  # noqa: E501
            'IS_NEW_MSG_GLOBAL_FIELD_ID': os.getenv('IS_NEW_MSG_GLOBAL_FIELD_ID'),  # noqa: E501
        }
        email_parser_config = {
            'PARSING_EMAIL_LOGIN': os.getenv('PARSING_EMAIL_LOGIN'),
            'PARSING_EMAIL_PSWD': os.getenv('PARSING_EMAIL_PSWD'),
            'PARSING_EMAIL_SERVER': os.getenv('PARSING_EMAIL_SERVER'),
            'PARSING_EMAIL_PORT': os.getenv('PARSING_EMAIL_PORT', 993),
        }
        Config.validate_env_variables(yt_manager_config)
        Config.validate_env_variables(email_parser_config)

        yt_manager = YandexTrackerManager(
            yt_manager_config['YT_CLIENT_ID'],
            yt_manager_config['YT_CLIENT_SECRET'],
            yt_manager_config['YT_ACCESS_TOKEN'],
            yt_manager_config['YT_REFRESH_TOKEN'],
            yt_manager_config['YT_ORGANIZATION_ID'],
            yt_manager_config['YT_QUEUE'],
            yt_manager_config['YT_DATABASE_GLOBAL_FIELD_ID'],
            yt_manager_config['YT_POLE_NUMBER_GLOBAL_FIELD_ID'],
            yt_manager_config['YT_BASE_STATION_GLOBAL_FIELD_ID'],
            yt_manager_config['YT_EMAIL_DATETIME_GLOBAL_FIELD_ID'],
            yt_manager_config['IS_NEW_MSG_GLOBAL_FIELD_ID'],
        )
        email_parser = EmailParser(
            email_parser_config['PARSING_EMAIL_LOGIN'],
            email_parser_config['PARSING_EMAIL_PSWD'],
            email_parser_config['PARSING_EMAIL_SERVER'],
            email_parser_config['PARSING_EMAIL_PORT'],
            yt_manager,
        )
        while True:
            try:
                email_parser.fetch_unread_emails()
            except KeyboardInterrupt:
                return
            except Exception as e:
                email_managment_logger.critical(e, exc_info=True)
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
