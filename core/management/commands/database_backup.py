import gzip
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path, PurePosixPath

import paramiko
from django.conf import settings
from django.core.management.base import BaseCommand

from core.constants import (
    DB_BACK_FILENAME_DATETIME_FORMAT,
    DB_BACK_FOLDER_DIR,
    MAX_DB_BACK,
    MAX_REMOTE_DB_BACK,
)
from core.loggers import default_logger
from core.wraps import timer


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
    remote_db_back_folder_dir = os.getenv('REMOTE_DB_BACK_FOLDER_DIR')

    missing_reserve_params = [
        name for name, value in {
            'RESERVE_SERVER_HOST': reserve_host,
            'RESERVE_SERVER_PORT': reserve_port,
            'RESERVE_SERVER_USERNAME': reserve_username,
            'RESERVE_SERVER_PASSWORD': reserve_password,
            'REMOTE_DB_BACK_FOLDER_DIR': remote_db_back_folder_dir,
        }.items() if value is None
    ]

    @timer(default_logger)
    def handle(self, *args, **options):
        self.backup_db()
        self.send_backup_on_reserve_server()
        self.cleanup_remote_backups()
        self.cleanup_old_backups()
        self.compress_old_remote_backups()

        # self.restore_database(
        #     (
        #         '/home/a.choliy/dispatch/data/remote_backup_db/'
        #         + 'backup_dispatch_2026-01-15_09-00.sql'
        #     ),
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
                    '-F', 'p',
                    '-b',
                    '--no-owner',
                    '-f', backup_file,
                    self.db_name,
                ],
                check=True
            )
            default_logger.info(f'Бэкап успешно создан: {backup_file}')
        except subprocess.CalledProcessError as e:
            default_logger.exception(e)
            raise

    def restore_database(self, dump_file: str, new_db_name: str) -> None:
        """
        Восстанавливает базу данных из дампа в новую БД.

        Args:
            dump_file(str): Путь к .sql файлу с резервной копией базы.
            new_db_name (str): Имя новой базы данных, куда восстановить
        """
        if not os.path.exists(dump_file):
            default_logger.error(
                f'Дамп файл "{dump_file}" отсутствует. Проверьте путь к файлу.'
            )
            return

        env = {
            'PGPASSWORD': self.db_pswd
        }

        create_db_cmd = [
            'psql',
            f'--host={self.db_host}',
            f'--port={self.db_port}',
            f'--username={self.db_user}',
            '-d', 'postgres',
            '-c',
            f'CREATE DATABASE {new_db_name};'
        ]

        subprocess.run(create_db_cmd, check=True, env=env)
        default_logger.info(f'База данных {new_db_name} создана')

        restore_cmd = [
            'psql',
            f'--host={self.db_host}',
            f'--port={self.db_port}',
            f'--username={self.db_user}',
            '--dbname', new_db_name,
            '-f', dump_file
        ]

        try:
            subprocess.run(
                restore_cmd,
                check=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            default_logger.info(
                f'Восстановление дампа в новую базу {new_db_name} завершено'
            )
        except subprocess.CalledProcessError as e:
            default_logger.exception(
                'Ошибка восстановления базы:\n'
                f'STDOUT: {e.stdout}\n'
                f'STDERR: {e.stderr}'
            )

    def cleanup_old_backups(self) -> None:
        """Удаляет .sql и .sql.gz дампы базы данных старше N дней."""
        now = datetime.now()
        cutoff_date = now - MAX_DB_BACK

        folder = Path(DB_BACK_FOLDER_DIR)

        for file in folder.iterdir():
            if not file.name.startswith(f'backup_{self.db_name}_'):
                continue

            if not (
                file.name.endswith('.sql') or file.name.endswith('.sql.gz')
            ):
                continue

            date_str = (
                file.name
                .replace(f'backup_{self.db_name}_', '')
                .replace('.sql.gz', '')
                .replace('.sql', '')
            )

            try:
                file_date = datetime.strptime(
                    date_str,
                    DB_BACK_FILENAME_DATETIME_FORMAT
                )
            except ValueError:
                default_logger.warning(
                    f'Пропущен файл (не удалось распарсить дату): {file.name}'
                )
                continue

            if file_date < cutoff_date:
                try:
                    file.unlink()
                    default_logger.info(
                        f'Удалён старый бэкап: {file.as_posix()}'
                    )
                except Exception as e:
                    default_logger.exception(
                        f'Ошибка при удалении {file.as_posix()}: {e}'
                    )

    def _sftp_upload(self, local_path: str, remote_path: str):
        if self.missing_reserve_params:
            default_logger.error(
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
            default_logger.info(
                'Файл успешно сохранен на удалённом сервере. '
                f'Путь: {remote_path}'
            )
        except (paramiko.SSHException, OSError) as e:
            default_logger.error(
                'Ошибка подключения или передачи данных на резервный '
                f'сервер: {e}'
            )
        except Exception as e:
            default_logger.exception(
                'Непредвиденная ошибка при передаче данных на резервный '
                f'сервер: {e}'
            )
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()

    def sftp_mkdirs(self, sftp: paramiko.SFTPClient, path: str):
        dirs = path.strip('/').split('/')
        current = ''
        for d in dirs:
            current += '/' + d
            try:
                sftp.stat(current)
            except FileNotFoundError:
                sftp.mkdir(current)

    def send_backup_on_reserve_server(self):
        """Сохраняет дампы базы данных на резервный сервер."""
        files_2_send = []
        remote_files = []

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
                default_logger.warning(
                    f'Пропущен файл (не удалось распарсить дату): {filename}'
                )
                continue

            file_path = os.path.join(DB_BACK_FOLDER_DIR, filename)
            files_2_send.append(file_path)

        if self.missing_reserve_params:
            default_logger.error(
                'Невозможно выполнить перенос бэкапов. '
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
                remote_files = sftp.listdir(self.remote_db_back_folder_dir)
            except IOError:
                default_logger.warning(
                    f'Не удалось прочитать удалённую директорию '
                    f'{self.remote_db_back_folder_dir}. '
                )
                self.sftp_mkdirs(sftp, self.remote_db_back_folder_dir)
                remote_files = []
        except Exception as e:
            default_logger.exception(
                'Ошибка при попытки чтения удаленной директории '
                f'{self.remote_db_back_folder_dir}: {e}'
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
            remote_file_path = os.path.join(
                self.remote_db_back_folder_dir, filename
            )
            self._sftp_upload(file_path, remote_file_path)

    def cleanup_remote_backups(self) -> None:
        """Удаляет старые .sql и .sql.gz бэкапы на удалённом сервере."""
        if self.missing_reserve_params:
            default_logger.error(
                'Невозможно выполнить удалённую очистку бэкапов. '
                'Отсутствуют параметры подключения: '
                f'{", ".join(self.missing_reserve_params)}'
            )
            return

        cutoff_date = datetime.now() - MAX_REMOTE_DB_BACK
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

            for filename in sftp.listdir(self.remote_db_back_folder_dir):
                if not filename.startswith(f'backup_{self.db_name}_'):
                    continue

                if not (
                    filename.endswith('.sql') or filename.endswith('.sql.gz')
                ):
                    continue

                date_str = (
                    filename
                    .replace(f'backup_{self.db_name}_', '')
                    .replace('.sql.gz', '')
                    .replace('.sql', '')
                )

                try:
                    file_date = datetime.strptime(
                        date_str,
                        DB_BACK_FILENAME_DATETIME_FORMAT
                    )
                except ValueError:
                    default_logger.warning(
                        f'Пропущен файл на удалённом сервере '
                        f'(не удалось распарсить дату): {filename}'
                    )
                    continue

                if file_date < cutoff_date:
                    remote_path = str(
                        PurePosixPath(self.remote_db_back_folder_dir)
                        / filename
                    )

                    try:
                        sftp.remove(remote_path)
                        default_logger.info(
                            f'Удалён старый: {remote_path}'
                        )
                    except Exception as e:
                        default_logger.exception(
                            f'Ошибка при удалении файла {remote_path}: {e}'
                        )

        except Exception as e:
            default_logger.exception(
                f'Ошибка при очистке бэкапов на удаленном сервере: {e}'
            )

        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()

    def gzip_compress(
        self, file_path: Path, del_original_file: bool = True
    ) -> Path:
        gz_path = file_path.with_suffix(file_path.suffix + '.gz')

        with open(file_path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        if del_original_file:
            os.remove(file_path)

        return gz_path

    def gzip_decompress(
        self,
        gz_path: Path,
        file_suffix: str = '',
        del_original_file: bool = True
    ) -> Path:
        file_path = gz_path.with_suffix(file_suffix)

        with gzip.open(gz_path, 'rb') as f_in:
            with open(file_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        if del_original_file:
            os.remove(gz_path)

        return file_path

    def compress_old_remote_backups(self) -> None:
        """
        Архивирует .sql файлы на удалённом сервере, возраст которых
        старше MAX_DB_BACK, но младше MAX_REMOTE_DB_BACK.
        """

        if self.missing_reserve_params:
            default_logger.error(
                'Невозможно выполнить архивацию бэкапов. '
                'Отсутствуют параметры: '
                f'{", ".join(self.missing_reserve_params)}'
            )
            return

        now = datetime.now()
        min_age = now - MAX_DB_BACK
        max_age = now - MAX_REMOTE_DB_BACK

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

            for filename in sftp.listdir(self.remote_db_back_folder_dir):
                if not filename.startswith(f'backup_{self.db_name}_'):
                    continue

                if not filename.endswith('.sql'):
                    continue

                date_str = (
                    filename
                    .replace(f'backup_{self.db_name}_', '')
                    .replace('.sql', '')
                )

                try:
                    file_date = datetime.strptime(
                        date_str, DB_BACK_FILENAME_DATETIME_FORMAT
                    )
                except ValueError:
                    default_logger.warning(
                        f'Пропущен файл (некорректная дата): {filename}'
                    )
                    continue

                if not (max_age < file_date < min_age):
                    continue

                remote_sql = str(
                    PurePosixPath(self.remote_db_back_folder_dir) / filename
                )
                remote_gz = remote_sql + '.gz'

                default_logger.info(
                    f'Архивация удалённого файла {remote_sql}'
                )

                # Скачиваем .sql во временный файл
                local_tmp = Path(DB_BACK_FOLDER_DIR) / f'__tmp_{filename}'
                sftp.get(remote_sql, str(local_tmp))

                # Сжимаем локально
                gz_local = self.gzip_compress(local_tmp)

                # Загружаем .gz обратно на сервер
                sftp.put(str(gz_local), remote_gz)

                # Удаляем локальные временные файлы
                gz_local.unlink(missing_ok=True)
                local_tmp.unlink(missing_ok=True)

                # Удаляем исходный .sql на сервере
                sftp.remove(remote_sql)

                default_logger.info(
                    f'Удалён оригинал и загружен архив: {remote_gz}'
                )

        except Exception as e:
            default_logger.exception(
                f'Ошибка архивации удалённых бэкапов: {e}'
            )
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()
