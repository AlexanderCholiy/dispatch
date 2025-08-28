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
from yandex_tracker.utils import yt_manager

email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'

    def handle(self, *args, **kwargs):
        email_parser_config = {
            'PARSING_EMAIL_LOGIN': os.getenv('PARSING_EMAIL_LOGIN'),
            'PARSING_EMAIL_PSWD': os.getenv('PARSING_EMAIL_PSWD'),
            'PARSING_EMAIL_SERVER': os.getenv('PARSING_EMAIL_SERVER'),
            'PARSING_EMAIL_PORT': os.getenv('PARSING_EMAIL_PORT', 993),
        }

        Config.validate_env_variables(email_parser_config)

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
