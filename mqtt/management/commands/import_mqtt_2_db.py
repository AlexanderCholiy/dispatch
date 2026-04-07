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
from mqtt.models import CellInfo, Device, DeviceOperator, Operator
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

                operators_to_save = []
                cells_to_save = []
                operators_dict = {}

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

                        processed_count += 1
                        current_event_time = validated_model.event_datetime
                        device_mac = validated_model.macaddress

                        device, _ = Device.objects.update_or_create(
                            mac_address=device_mac,
                            defaults={
                                'gps_lat': (
                                    validated_model.gps.lat
                                    if validated_model.gps else None
                                ),
                                'gps_lon': (
                                    validated_model.gps.lon
                                    if validated_model.gps else None
                                ),
                                'sys_version': validated_model.sysversion,
                                'app_version': validated_model.appversion,
                                'last_seen': current_event_time,
                            }
                        )

                        current_operator_codes = set()
                        if (
                            validated_model.aops
                            and validated_model.aops.operators
                        ):
                            for op_data in validated_model.aops.operators:
                                code = op_data.operator_code
                                current_operator_codes.add(code)

                                if code not in operators_dict:
                                    operator_obj, created_op = (
                                        Operator.objects.get_or_create(
                                            code=code,
                                            defaults={
                                                'name': op_data.operator_name
                                            }
                                        )
                                    )
                                    operators_dict[code] = operator_obj

                                    if (
                                        not created_op
                                        and op_data.operator_name
                                        and not operator_obj.name
                                    ):
                                        operator_obj.name = (
                                            op_data.operator_name
                                        )
                                        operator_obj.save(
                                            update_fields=['name']
                                        )

                                operators_to_save.append(DeviceOperator(
                                    device=device,
                                    operator=operators_dict[code],
                                    index=op_data.index,
                                    status=(
                                        op_data.status.value
                                        if op_data.status else None
                                    ),
                                    last_seen=current_event_time
                                ))

                        if validated_model.aops and validated_model.aops.cells:
                            for cell_data in validated_model.aops.cells:
                                if not cell_data.cellid:
                                    continue

                                cells_to_save.append(CellInfo(
                                    device=device,
                                    index=cell_data.index,
                                    cell_id=cell_data.cellid,
                                    event_datetime=current_event_time,
                                    mcc_mnc=cell_data.mcc_mnc,
                                    network_type=(
                                        cell_data.net_type.value
                                        if cell_data.net_type else None
                                    ),
                                    freq=cell_data.freq,
                                    tac=cell_data.tac,
                                    lac=cell_data.lac,
                                    rsrp=cell_data.rsrp,
                                    rsrq=cell_data.rsrq,
                                    pci=cell_data.pci,
                                    earfcn=cell_data.earfcn,
                                    rscp=cell_data.rscp,
                                    ecno=cell_data.ecno,
                                    psc=cell_data.psc,
                                    rssi=cell_data.rssi,
                                    rxlev=cell_data.rxlev,
                                    bsic=cell_data.bsic,
                                    c1=cell_data.c1,
                                ))

                        if (
                            len(operators_to_save) >= MQTT_DB_BATCH_SIZE
                            or len(cells_to_save) >= MQTT_DB_BATCH_SIZE
                        ):
                            self._flush_to_db(operators_to_save, cells_to_save)

                            operators_to_save = []
                            cells_to_save = []

                            (
                                DeviceOperator.objects
                                .filter(device=device)
                                .exclude(
                                    operator__code__in=current_operator_codes
                                )
                                .delete()
                            )

                self._flush_to_db(operators_to_save, cells_to_save)

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

    def _flush_to_db(self, operators_list, cells_list):
        """Выполняет массовую запись в БД"""
        try:
            if cells_list:
                CellInfo.objects.bulk_create(
                    cells_list, ignore_conflicts=True
                )

            if operators_list:
                DeviceOperator.objects.bulk_create(
                    operators_list, ignore_conflicts=True
                )

        except Exception:
            mqtt_logger.exception(
                'Ошибка при пакетной записи CellInfo и DeviceOperator в БД.'
            )
