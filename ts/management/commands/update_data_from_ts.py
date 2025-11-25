import os
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from core.constants import TS_LOG_ROTATING_FILE, UPDATE_DATA_FROM_TS_LOCK_FILE
from core.loggers import LoggerFactory
from core.wraps import timer
from ts.api import Api
from ts.constants import TS_DATA_DIR

ts_managment_logger = LoggerFactory(
    __name__, TS_LOG_ROTATING_FILE
).get_logger()


class Command(BaseCommand):
    help = 'Обновление таблиц опор, БС, операторов и подрядчиков по АВР'

    @timer(ts_managment_logger, False)
    def handle(self, *args, **kwargs):
        lock_acquired = False
        now = datetime.now()
        lock_timeout = timedelta(hours=3)

        if os.path.exists(UPDATE_DATA_FROM_TS_LOCK_FILE):
            try:
                with open(UPDATE_DATA_FROM_TS_LOCK_FILE) as f:
                    content = f.read()
                    ts_time_str = (
                        content.split('|')[1]
                    ) if '|' in content else None
                    ts_time = datetime.fromisoformat(
                        ts_time_str
                    ) if ts_time_str else None

                if ts_time and now - ts_time < lock_timeout:
                    ts_managment_logger.warning(
                        'Данные TowerStore ещё обновляются, пропуск запуска'
                    )
                    return
                else:
                    ts_managment_logger.warning(
                        f'Lock-файл {UPDATE_DATA_FROM_TS_LOCK_FILE} устарел, '
                        'перезаписываем'
                    )
            except Exception:
                ts_managment_logger.exception(
                    'Не удалось прочитать lock-файл '
                    f'{UPDATE_DATA_FROM_TS_LOCK_FILE}, перезаписываем'
                )

        try:
            with open(UPDATE_DATA_FROM_TS_LOCK_FILE, 'w') as f:
                f.write(f'{os.getpid()}|{now.isoformat()}')
            lock_acquired = True

            os.makedirs(TS_DATA_DIR, exist_ok=True)
            ts_api = Api()
            ts_api.update_poles()
            ts_api.update_avr()
            ts_api.update_base_stations()

        finally:
            if lock_acquired and os.path.exists(UPDATE_DATA_FROM_TS_LOCK_FILE):
                os.remove(UPDATE_DATA_FROM_TS_LOCK_FILE)
