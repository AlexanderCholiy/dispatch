import csv
import os
import shutil
import subprocess
from typing import TypedDict

from django.core.cache import cache
from django.core.management.base import BaseCommand
from pydantic import ValidationError
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import monitoring_rvr_sms_logger
from core.wraps import timer
from monitoring.constants import (
    SMS_RVR_CONTROLLER_HOST,
    SMS_RVR_CONTROLLER_PSWD,
    SMS_RVR_CSV_FILE,
    SMS_RVR_DIR,
    SMS_RVR_LOCK_KEY,
    SMS_RVR_LOCK_TIMEOUT,
    SMS_RVR_TMP_FILE,
)
from monitoring.services.parse_sms_file import parse_sms_file


class NearestDevice(TypedDict):
    pole: str
    distance: float
    address: str


class Command(BaseCommand):
    help = 'Подготовка CSV файла с оповещениями по СМС о проведении РВР'

    _error_cnt = 0

    @timer(monitoring_rvr_sms_logger)
    def handle(self, *args, **kwargs):
        acquired = cache.add(
            SMS_RVR_LOCK_KEY, str(os.getpid()),
            timeout=SMS_RVR_LOCK_TIMEOUT
        )

        if not acquired:
            ttl = cache.ttl(SMS_RVR_LOCK_KEY)

            if ttl is None:
                acquired = cache.add(
                    SMS_RVR_LOCK_KEY,
                    str(os.getpid()),
                    timeout=SMS_RVR_LOCK_TIMEOUT
                )

            monitoring_rvr_sms_logger.warning(
                'Задача подготовки CSV с оповещениями по СМС о проведении РВР '
                'уже запущена. Пропуск.'
            )
            return

        try:
            self.copy_sms_from_controller()
            self.update_sms_csv()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            monitoring_rvr_sms_logger.exception(
                'Ошибка подготовки CSV'
                f' с РВР по СМС: {e}'
            )
        finally:
            cache.delete(SMS_RVR_LOCK_KEY)

            if SMS_RVR_TMP_FILE.exists():
                SMS_RVR_TMP_FILE.unlink()

    def copy_sms_from_controller(self):
        SMS_RVR_DIR.mkdir(parents=True, exist_ok=True)
        command = [
            'sshpass', '-p', SMS_RVR_CONTROLLER_PSWD,
            'rsync', '-avh', '--ignore-existing',
            '-e',
            'ssh -o StrictHostKeyChecking=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa',  # noqa: E501
            f'root@{SMS_RVR_CONTROLLER_HOST}:/var/spool/sms/incoming',
            str(SMS_RVR_DIR)
        ]

        incoming_path = SMS_RVR_DIR / 'incoming'

        try:
            subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

            if incoming_path.exists() and incoming_path.is_dir():
                for item in incoming_path.iterdir():
                    dest_item = SMS_RVR_DIR / item.name

                    if dest_item.exists() and dest_item.is_file():
                        dest_item.unlink()

                    shutil.move(str(item), str(dest_item))

                incoming_path.rmdir()
                monitoring_rvr_sms_logger.debug(
                    f'Папка {incoming_path} удалена.'
                )
            else:
                monitoring_rvr_sms_logger.warning(
                    'Папка /var/spool/sms/incoming пуста'
                )

            monitoring_rvr_sms_logger.debug(
                f'SMS с контроллера скопированы в: {SMS_RVR_DIR}'
            )
        except subprocess.CalledProcessError as e:
            monitoring_rvr_sms_logger.exception(
                f'Ошибка при выполнении команды '
                f'копирования СМС с контроллера: {e}'
            )

    def _log_error(self, error: Exception, filename: str):
        if self._error_cnt == 0:
            monitoring_rvr_sms_logger.exception(
                f'Ошибка обработки {filename}: {str(error)}'
            )
        else:
            monitoring_rvr_sms_logger.debug(
                f'Ошибка обработки {filename}: {str(error)}', exc_info=True
            )
        self._error_cnt += 1

    def update_sms_csv(self):
        files_processed = 0
        files_err = 0

        total = len(list(SMS_RVR_DIR.iterdir()))

        fieldnames = [
            'phone_from',
            'received_time',
            'answer',
        ]
        excel_dt_format = '%Y-%m-%d %H:%M'

        SMS_RVR_TMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        SMS_RVR_CSV_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(
            SMS_RVR_TMP_FILE, mode='w', newline='', encoding='utf-8-sig'
        ) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            with tqdm(
                total=total,
                desc='Подготовка CSV файла с оповещениями РВР по СМС',
                colour='cyan',
                position=0,
                leave=True,
                disable=not DEBUG_MODE,
            ) as pbar_outer:
                for item in SMS_RVR_DIR.iterdir():
                    if not item.is_file():
                        pbar_outer.update(1)
                        continue

                    try:
                        sms = parse_sms_file(item)

                        if not sms:
                            pbar_outer.update(1)
                            item.unlink()
                            monitoring_rvr_sms_logger.debug(
                                f'Удален пустой файл: {item.name}'
                            )
                            continue

                        received_time = (
                            sms.received_time.strftime(excel_dt_format)
                            if sms.received_time else None
                        )

                        record = {
                            'phone_from': sms.phone_from,
                            'received_time': received_time,
                            'answer': sms.answer,
                        }
                        writer.writerow(record)

                        files_processed += 1

                    except ValidationError as e:
                        self._log_error(e, item.name)
                        files_err += 1

                    except UnicodeDecodeError:
                        monitoring_rvr_sms_logger.warning(
                            f'Ошибка кодирования в файле {item.name}'
                        )
                        files_err += 1

                    except KeyboardInterrupt:
                        raise

                    except Exception as e:
                        monitoring_rvr_sms_logger.exception(
                            f'Не удалось прочитать {item.name}: {e}'
                        )
                        files_err += 1

                    pbar_outer.update(1)

        shutil.move(str(SMS_RVR_TMP_FILE), str(SMS_RVR_CSV_FILE))

        if files_processed == 0:
            monitoring_rvr_sms_logger.debug(
                f'Файлов в {SMS_RVR_DIR} пока нет.'
            )
        if files_err > 0:
            monitoring_rvr_sms_logger.warning(
                f'Обработано {files_processed}; '
                f'Ошибок: {files_err}; '
                f'Всего: {total}'
            )
