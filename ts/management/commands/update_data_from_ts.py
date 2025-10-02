import os

from django.core.management.base import BaseCommand

from core.constants import TS_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from core.tg_bot import tg_manager
from core.wraps import timer
from ts.api import Api
from ts.constants import TS_DATA_DIR

ts_managment_logger = LoggerFactory(__name__, TS_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление таблиц опор, БС, операторов и подрядчиков по АВР'

    @timer(ts_managment_logger)
    def handle(self, *args, **kwargs):
        tg_manager.send_startup_notification(__name__)

        os.makedirs(TS_DATA_DIR, exist_ok=True)
        # Api.update_poles()  # данные по опорам обновляем в первую очередь
        Api.update_avr(False)
        # Api.update_base_stations()

        tg_manager.send_success_notification(__name__)
