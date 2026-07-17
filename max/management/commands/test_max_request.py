from django.core.management.base import BaseCommand

from core.loggers import max_api_logger
from core.wraps import timer

from max.max_api import max_api


class Command(BaseCommand):
    help = 'Тестирование мессенджера MAX.'

    @timer(max_api_logger)
    def handle(self, *args, **options):
        max_api.check_updates()
