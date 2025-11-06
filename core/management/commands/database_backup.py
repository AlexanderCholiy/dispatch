import os
import subprocess
from datetime import datetime, timedelta

import paramiko
from django.conf import settings
from django.core.management.base import BaseCommand

from core.constants import (
    DB_BACK_FILENAME_DATETIME_FORMAT,
    DB_BACK_FOLDER_DIR,
    MAX_DB_BACK,
    MAX_REMOTE_DB_BACK,
    REMOTE_DB_BACK_FOLDER_DIR,
)
from core.loggers import LoggerFactory
from core.wraps import timer

bakup_manager_logger = LoggerFactory(__name__).get_logger()


class Command(BaseCommand):
    help = 'Резервная копия базы данных, с ротацией N дней.'

    database_conf: dict = settings.DATABASES['default']

    db_host = database_conf['HOST']
    db_port = database_conf['PORT']
    db_name = database_conf['NAME']
    db_user = database_conf['USER']
    db_pswd = database_conf['PASSWORD']

    reserve_host = os.getenv('RESERVE_SERVER_HOST')
    reserve_port = int(os.getenv('RESERVE_SERVER_PORT', 22))
    reserve_username = os.getenv('RESERVE_SERVER_USERNAME')
    reserve_password = os.getenv('RESERVE_SERVER_PASSWORD')

    missing_reserve_params = [
        name for name, value in {
            'RESERVE_SERVER_HOST': reserve_host,
            'RESERVE_SERVER_PORT': reserve_port,
            'RESERVE_SERVER_USERNAME': reserve_username,
            'RESERVE_SERVER_PASSWORD': reserve_password,
        }.items() if value is None
    ]

    @timer(bakup_manager_logger)
    def handle(self, *args, **options):
        self.backup_db()
        self.send_backup_on_reserve_server(REMOTE_DB_BACK_FOLDER_DIR)
        self.cleanup_remote_backups(
            MAX_REMOTE_DB_BACK, REMOTE_DB_BACK_FOLDER_DIR
        )
        self.cleanup_old_backups(MAX_DB_BACK)
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

    def cleanup_old_backups(self, dt: timedelta) -> None:
        """Удаляет дампы базы данных старше N дней."""
        now = datetime.now()
        cutoff_date = now - dt

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

    def _sftp_upload(self, local_path: str, remote_path: str):
        if self.missing_reserve_params:
            bakup_manager_logger.error(
                'Невозможно выполнить передачу резервной копии на удалённый '
                'сервер. Отсутствуют параметры подключения: '
                f'{", ".join(self.missing_reserve_params)}'
            )
            return

        transport = None
        sftp = None

        try:
            transport = paramiko.Transport(
                (self.reserve_host, self.reserve_port)
            )
            transport.connect(
                username=self.reserve_username,
                password=self.reserve_password
            )

            sftp = paramiko.SFTPClient.from_transport(transport)

            remote_dir = os.path.dirname(remote_path)
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                dirs = remote_dir.split('/')
                current = ''
                for d in dirs:
                    if not d:
                        continue
                    current = f'{current}/{d}'
                    try:
                        sftp.stat(current)
                    except FileNotFoundError:
                        sftp.mkdir(current)

            sftp.put(local_path, remote_path)
            bakup_manager_logger.info(
                'Файл успешно сохранен на удалённом сервере. '
                f'Путь: {remote_path}'
            )
        except (paramiko.SSHException, OSError) as e:
            bakup_manager_logger.error(
                'Ошибка подключения или передачи данных на резервный '
                f'сервер: {e}'
            )
        except Exception as e:
            bakup_manager_logger.exception(
                'Непредвиденная ошибка при передаче данных на резервный '
                f'сервер: {e}'
            )
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()

    def send_backup_on_reserve_server(self, remote_path: str):
        """Сохраняет дампы базы данных на резервный сервер."""
        files_2_send = []

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
                datetime.strptime(
                    date_str, DB_BACK_FILENAME_DATETIME_FORMAT
                )
            except ValueError:
                bakup_manager_logger.warning(
                    f'Пропущен файл (не удалось распарсить дату): {filename}'
                )
                continue

            file_path = os.path.join(DB_BACK_FOLDER_DIR, filename)
            files_2_send.append(file_path)

        if self.missing_reserve_params:
            bakup_manager_logger.error(
                'Невозможно выполнить удалённую очистку бэкапов. '
                'Отсутствуют параметры подключения: '
                f'{", ".join(self.missing_reserve_params)}'
            )
            return

        transport = None
        sftp = None

        try:
            transport = paramiko.Transport(
                (self.reserve_host, self.reserve_port)
            )
            transport.connect(
                username=self.reserve_username, password=self.reserve_password
            )
            sftp = paramiko.SFTPClient.from_transport(transport)
            try:
                remote_files = sftp.listdir(remote_path)
            except IOError:
                bakup_manager_logger.warning(
                    f'Не удалось прочитать удалённую директорию '
                    f'{remote_path}. '
                )
                sftp.mkdir(remote_path)
                remote_files = []
        except Exception as e:
            bakup_manager_logger.exception(
                'Ошибка при попытки чтения удаленной директории '
                f'{remote_path}: {e}'
            )
        finally:
            try:
                sftp.close()
            except Exception:
                pass

        files_2_send = [
            f for f in files_2_send if os.path.basename(f) not in remote_files
        ]

        for file_path in files_2_send:
            filename = os.path.basename(file_path)
            remote_file_path = os.path.join(remote_path, filename)
            self._sftp_upload(file_path, remote_file_path)

    def cleanup_remote_backups(self, dt: timedelta, remote_dir: str) -> None:
        """Удаляет старые SQL-бэкапы на удалённом сервере."""
        if self.missing_reserve_params:
            bakup_manager_logger.error(
                'Невозможно выполнить удалённую очистку бэкапов. '
                'Отсутствуют параметры подключения: '
                f'{", ".join(self.missing_reserve_params)}'
            )
            return

        cutoff_date = datetime.now() - dt
        transport = None
        sftp = None

        try:
            transport = paramiko.Transport(
                (self.reserve_host, self.reserve_port)
            )
            transport.connect(
                username=self.reserve_username, password=self.reserve_password
            )
            sftp = paramiko.SFTPClient.from_transport(transport)

            for filename in sftp.listdir(remote_dir):
                if (
                    not filename.startswith(f'backup_{self.db_name}_')
                    or not filename.endswith('.sql')
                ):
                    continue

                try:
                    date_str = (
                        filename
                        .replace(f'backup_{self.db_name}_', '')
                        .replace('.sql', '')
                    )
                    file_date = datetime.strptime(
                        date_str, DB_BACK_FILENAME_DATETIME_FORMAT
                    )
                except ValueError:
                    bakup_manager_logger.warning(
                        f'Пропущен файл на удалённом сервере: {filename}'
                    )
                    continue

                if file_date < cutoff_date:
                    remote_file = os.path.join(remote_dir, filename)
                    sftp.remove(remote_file)
                    bakup_manager_logger.info(
                        f'Удалён старый удалённый бэкап: {remote_file}'
                    )

        except Exception as e:
            bakup_manager_logger.exception(
                f'Ошибка при удалённой очистке бэкапов: {e}'
            )
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()
