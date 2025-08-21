from django.core.management.base import BaseCommand

from core.wraps import timer
from core.loggers import LoggerFactory
from core.constants import EMAIL_LOG_ROTATING_FILE


email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'

    @timer(email_managment_logger)
    def handle(self, *args, **kwargs):
        ...
