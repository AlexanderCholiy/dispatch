import os

from django.core.management.base import BaseCommand

from core.constants import LOG_DIR
from core.loggers import default_logger


class Command(BaseCommand):
    help = 'Рекурсивно очищает все .log файлы в директории логов'

    def handle(self, *args, **options):
        if not os.path.exists(LOG_DIR):
            default_logger.warning(f'LOG_DIR не существует: {LOG_DIR}')
            return

        total_logs = 0
        cleared_logs = 0
        total_bytes = 0

        for root, _, files in os.walk(LOG_DIR):
            for file in files:
                if not file.endswith('.log'):
                    continue

                total_logs += 1
                file_path = os.path.join(root, file)

                try:
                    size = os.path.getsize(file_path)
                    if size == 0:
                        continue

                    total_bytes += size

                    with open(file_path, 'w', encoding='utf-8'):
                        pass

                    cleared_logs += 1

                except Exception:
                    default_logger.exception(f'Ошибка доступа к {file_path}')

        if cleared_logs:
            default_logger.info(
                f'Логи: найдено={total_logs}, очищено={cleared_logs}, '
                f'освобождено={total_bytes / 1024 / 1024:.2f} MB'
            )
