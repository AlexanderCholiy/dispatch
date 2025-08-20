import os

from django.core.management.base import BaseCommand

from ts.constants import TS_DATA_DIR, POLES_FILE, BASE_STATIONS_FILE, AVR_FILE
from core.wraps import timer
from core.constants import TS_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from ts.api import Api


ts_managment_logger = LoggerFactory(__name__, TS_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление таблиц опор, БС, операторов и подрядчиков по АВР'

    @timer(ts_managment_logger)
    def handle(self, *args, **kwargs):
        os.makedirs(TS_DATA_DIR, exist_ok=True)

        # Api.update_poles()
        # Api.update_avr()
        Api.update_base_stations()
