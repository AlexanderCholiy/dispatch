import os
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from core.constants import UPDATE_DATA_FROM_TS_LOCK_FILE
from core.loggers import ts_logger
from core.wraps import timer
from ts.api import Api
from ts.constants import TS_DATA_DIR


class Command(BaseCommand):
    help = 'Обновление таблиц опор, БС, операторов и подрядчиков по АВР'

    @timer(ts_logger, False)
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
                    ts_logger.warning(
                        'Данные TowerStore ещё обновляются, пропуск запуска'
                    )
                    return
                else:
                    ts_logger.warning(
                        f'Lock-файл {UPDATE_DATA_FROM_TS_LOCK_FILE} устарел, '
                        'перезаписываем'
                    )
            except Exception:
                ts_logger.exception(
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
            ts_api.update_rvr()
            ts_api.update_avr()
            ts_api.update_base_stations()

        except Exception as e:
            ts_logger.exception(e)

        finally:
            if lock_acquired and os.path.exists(UPDATE_DATA_FROM_TS_LOCK_FILE):
                os.remove(UPDATE_DATA_FROM_TS_LOCK_FILE)
