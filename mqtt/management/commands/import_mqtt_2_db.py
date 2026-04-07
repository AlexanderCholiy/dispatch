from bson.objectid import ObjectId
from django.core.management.base import BaseCommand
from pydantic import ValidationError
from pymongo import MongoClient, errors
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import mqtt_logger
from core.wraps import timer
from mqtt.constants import (
    MQTT_BATCH_SIZE,
    MQTT_CONN_TIMEOUT,
    MQTT_MONGO_DB_COLLECTION,
    MQTT_MONGO_DB_NAME,
    MQTT_MONGO_DB_URL,
)
from mqtt.shemas.modem_data import ModemData


class Command(BaseCommand):
    help = 'Импорт данных о радиопокрытии вблизи АМС НБ из MongoDB в БД'

    _error_cnt = 0

    def handle(self, *args, **options):
        self.import_mqtt_2_db()

    def check_mongodb_connection(self):
        client = MongoClient(MQTT_MONGO_DB_URL)

        client.admin.command('ping')
        mqtt_logger.debug('Сервер отвечает')

    @timer(mqtt_logger, False)
    def import_mqtt_2_db(self):
        try:
            with MongoClient(
                MQTT_MONGO_DB_URL, serverSelectionTimeoutMS=MQTT_CONN_TIMEOUT
            ) as client:
                db = client[MQTT_MONGO_DB_NAME]
                collection = db[MQTT_MONGO_DB_COLLECTION]

                query = {
                    '_id': {'$gte': ObjectId('69c600000000000000000000')},
                    # MAC-адрес не пустой:
                    'data.modem.macaddress': {'$nin': [None, '', 'undefined']}
                }
                total_docs = collection.count_documents(query)

                if total_docs == 0:
                    mqtt_logger.warning('Нет данных для импорта.')
                    return

                cursor = collection.find(query).batch_size(MQTT_BATCH_SIZE)

                with tqdm(
                    cursor,
                    total=total_docs,
                    desc='Обработка данных MQTT из MongoDB',
                    colour='green',
                    position=0,
                    leave=True,
                    disable=not DEBUG_MODE,
                ) as progress_cursor:
                    for doc in progress_cursor:
                        self._process_document(doc)

                if self._error_cnt:
                    mqtt_logger.warning(
                        'Не удалось обработать '
                        f'{self._error_cnt} / {total_docs} записей.'
                    )

        except errors.ServerSelectionTimeoutError:
            mqtt_logger.error('Таймаут подключения к MongoDB.')
        except KeyboardInterrupt:
            return
        except Exception as e:
            mqtt_logger.exception(e)

    def _process_document(self, doc: dict):
        try:
            data: dict = doc.get('data', {})
            if not data or not isinstance(data, dict):
                return

            modem_raw: dict = data.get('modem', {})
            if not modem_raw or not isinstance(modem_raw, dict):
                return

            validated_model = ModemData.model_validate(modem_raw)

        except ValidationError as e:
            if not self._error_cnt:
                mqtt_logger.exception(f'Ошибка валидации данных: {str(e)}')
            else:
                first_error = e.errors()[0]
                field_name = first_error.get('loc', ['unknown'])[0]
                msg = (
                    f'Ошибка валидации поля "{field_name}": '
                    f'{first_error.get("msg", "Unknown error")}'
                )
                mqtt_logger.warning(msg)

            self._error_cnt += 1

        except KeyboardInterrupt:
            raise
        except Exception as e:
            if not self._error_cnt:
                mqtt_logger.exception(e)
            else:
                mqtt_logger.error(e)

            self._error_cnt += 1
