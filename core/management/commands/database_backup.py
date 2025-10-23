import os
import subprocess
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from core.constants import (
    DB_BACK_FILENAME_DATETIME_FORMAT,
    DB_BACK_FOLDER_DIR,
    MAX_DAYS_DB_BACK,
)
from core.loggers import LoggerFactory

bakup_manager_logger = LoggerFactory(__name__).get_logger()


class Command(BaseCommand):
    help = 'Резервная копия базы данных, с ротацией N дней.'

    database_conf: dict = settings.DATABASES['default']

    db_host = database_conf['HOST']
    db_port = database_conf['PORT']
    db_name = database_conf['NAME']
    db_user = database_conf['USER']
    db_pswd = database_conf['PASSWORD']

    def handle(self, *args, **options):
        self.backup_db()
        self.cleanup_old_backups(MAX_DAYS_DB_BACK)
        # self.restore_database(
        #     'backup_dispatch_backend_2025-09-10_15-16.sql',
        #     f'dump_{self.db_name}'
        # )

    def backup_db(self):
        """Резервная копия базы данных."""
        now = datetime.now().strftime(DB_BACK_FILENAME_DATETIME_FORMAT)

        backup_filename = f'backup_{self.db_name}_{now}.sql'
        backup_file = os.path.join(DB_BACK_FOLDER_DIR, backup_filename)

        os.environ['PGPASSWORD'] = self.db_pswd

        try:
            subprocess.run(
                [
                    'pg_dump',
                    '-h', self.db_host,
                    '-p', str(self.db_port),
                    '-U', self.db_user,
                    '-F', 'c',
                    '-b',
                    '-f', backup_file,
                    self.db_name,
                ],
                check=True
            )
            bakup_manager_logger.info(f'Бэкап успешно создан: {backup_file}')
        except subprocess.CalledProcessError as e:
            bakup_manager_logger.exception(e)
            raise

    def restore_database(self, dump_filename: str, new_db_name: str) -> None:
        """
        Восстанавливает базу данных из дампа в новую БД.

        Args:
            dump_file(str): Название .sql файла с резервной копией базы.
            new_db_name (str): Имя новой базы данных, куда восстановить
        """
        create_db_cmd = [
            'psql',
            f'--host={self.db_host}',
            f'--port={self.db_port}',
            f'--username={self.db_user}',
            '-d', 'postgres',
            '-c',
            f'CREATE DATABASE {new_db_name};'
        ]

        dump_file = os.path.join(DB_BACK_FOLDER_DIR, dump_filename)

        restore_cmd = [
            'pg_restore',
            f'--host={self.db_host}',
            f'--port={self.db_port}',
            f'--username={self.db_user}',
            '--dbname', new_db_name,
            dump_file
        ]

        env = {
            'PGPASSWORD': self.db_pswd
        }

        subprocess.run(create_db_cmd, check=True, env=env)
        bakup_manager_logger.info(f'База данных {new_db_name} создана')

        subprocess.run(restore_cmd, check=True, env=env)
        bakup_manager_logger.info(
            f'Восстановление дампа в новую базу {new_db_name} завершено')

    def cleanup_old_backups(self, days: int = 7) -> None:
        """Удаляет дампы базы данных старше N дней."""
        now = datetime.now()
        cutoff_date = now - timedelta(days=days)

        for filename in os.listdir(DB_BACK_FOLDER_DIR):
            if (
                not filename.startswith('backup_')
                or not filename.endswith('.sql')
            ):
                continue

            try:
                date_str = (
                    filename.replace(f'backup_{self.db_name}_', '')
                    .replace('.sql', '')
                )
                file_date = datetime.strptime(
                    date_str, DB_BACK_FILENAME_DATETIME_FORMAT)
            except ValueError:
                bakup_manager_logger.warning(
                    f'Пропущен файл (не удалось распарсить дату): {filename}')
                continue

            if file_date < cutoff_date:
                file_path = os.path.join(DB_BACK_FOLDER_DIR, filename)
                try:
                    os.remove(file_path)
                    bakup_manager_logger.info(
                        f'Удалён старый бэкап: {file_path}')
                except OSError as e:
                    bakup_manager_logger.exception(
                        f'Ошибка при удалении {file_path}: {e}')
