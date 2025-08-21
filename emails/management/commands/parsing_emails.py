import os

from django.core.management.base import BaseCommand

from core.constants import EMAIL_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from core.wraps import timer
from emails.email_parser import EmailParser

email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'

    @timer(email_managment_logger)
    def handle(self, *args, **kwargs):
        email_parser = EmailParser(
            os.getenv('PARSING_EMAIL_LOGIN'),
            os.getenv('PARSING_EMAIL_PSWD'),
            os.getenv('PARSING_EMAIL_SERVER'),
            os.getenv('PARSING_EMAIL_PORT', 993),
        )
        email_parser.fetch_unread_emails()
