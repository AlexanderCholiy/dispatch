from django.core.management.base import BaseCommand

from yandex_tracker.utils import YandexTrackerManager
from core.constants import YANDEX_TRACKER_ROTATING_FILE
from core.loggers import LoggerFactory
from core.wraps import timer

email_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

    @timer(email_managment_logger)
    def handle(self, *args, **kwargs):
        result = YandexTrackerManager().current_user_info
        print(result)
