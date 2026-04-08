from typing import Optional

from bson.objectid import ObjectId
from django.core.management.base import BaseCommand
from django.utils import timezone
from pydantic import ValidationError
from pymongo import MongoClient, errors
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import mqtt_logger
from core.wraps import timer
from mqtt.constants import (
    MONGO_RETENTION_TTL,
    MQTT_BATCH_SIZE,
    MQTT_CONN_TIMEOUT,
    MQTT_DB_BATCH_SIZE,
    MQTT_MONGO_DB_COLLECTION,
    MQTT_MONGO_DB_NAME,
    MQTT_MONGO_DB_URL,
)
from mqtt.models import Device, Operator, Cell, CellMeasure
from mqtt.shemas.modem_data import ModemData


class Command(BaseCommand):
    help = 'Импорт данных о радиопокрытии из MongoDB в БД'
    _error_cnt = 0

    def handle(self, *args, **options):
        self.import_mqtt_2_db()

    @timer(mqtt_logger, False)
    def import_mqtt_2_db(self):
        try:
            with MongoClient(
                MQTT_MONGO_DB_URL, serverSelectionTimeoutMS=MQTT_CONN_TIMEOUT
            ) as client:
                db = client[MQTT_MONGO_DB_NAME]
                collection = db[MQTT_MONGO_DB_COLLECTION]

                cutoff_date = timezone.now() - MONGO_RETENTION_TTL
                date_filter_str = cutoff_date.strftime("%d.%m.%Y")

                query = {
                    '_id': {'$gte': ObjectId('69c600000000000000000000')},
                    'data.modem.macaddress': {'$nin': [None, '', 'undefined']},
                    'data.modem.date': {'$gte': date_filter_str}
                }

                total_docs = collection.count_documents(query)
                if total_docs == 0:
                    mqtt_logger.warning('Нет данных для импорта.')
                    return

                cursor = collection.find(query).batch_size(MQTT_BATCH_SIZE)

                processed_count = 0

                with tqdm(
                    cursor,
                    total=total_docs,
                    desc='Обработка и подготовка',
                    colour='green',
                    position=0,
                    leave=True,
                    disable=not DEBUG_MODE,
                ) as progress_cursor:

                    for doc in progress_cursor:
                        validated_model = self._process_document(doc)

                        if not validated_model:
                            continue

                if self._error_cnt:
                    mqtt_logger.warning(
                        f'Не удалось обработать {self._error_cnt} '
                        f'/ {total_docs} записей.'
                    )
                else:
                    mqtt_logger.info(
                        f'Успешно импортировано {processed_count} записей.'
                    )

        except errors.ServerSelectionTimeoutError:
            mqtt_logger.error('Таймаут подключения к MongoDB.')
        except KeyboardInterrupt:
            mqtt_logger.warning('Процесс прерван.')
        except Exception as e:
            mqtt_logger.exception(e)

    def _process_document(self, doc: dict) -> Optional[ModemData]:
        """Возвращает валидированную модель или None"""
        try:
            data = doc.get('data', {})
            if not isinstance(data, dict):
                return None

            modem_raw = data.get('modem', {})
            if not isinstance(modem_raw, dict):
                return None

            return ModemData.model_validate(modem_raw)

        except ValidationError as e:
            if not self._error_cnt:
                mqtt_logger.exception(f'Ошибка валидации: {str(e)}')
            else:
                first_error = e.errors()[0]
                field_name = first_error.get('loc', ['unknown'])[0]
                mqtt_logger.warning(
                    f'Ошибка поля "{field_name}": {first_error.get("msg")}'
                )
            self._error_cnt += 1
        except Exception as e:
            if not self._error_cnt:
                mqtt_logger.exception(e)
            else:
                mqtt_logger.error(e)
            self._error_cnt += 1
        return None
