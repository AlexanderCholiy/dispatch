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

    _devices_mac_in_db: set[str] = set(
        Device.objects.values_list('mac_address', flat=True)
    )
    _devices_to_create: dict[str, Device] = {}
    _devices_to_update: dict[str, Device] = {}

    _operators_code_in_db: set[str] = set(
        Operator.objects.values_list('code', flat=True)
    )
    _operators_to_create: dict[str, Operator] = {}

    # Ключ для сот: (operator_code, cell_id) -> объект Cell
    _cells_id_operator_in_db: set[tuple[str, int]] = set(
        Cell.objects.values_list('operator__code', 'cell_id')
    )
    _cells_to_create: dict[tuple[str, int], Cell] = {}
    _cells_to_update: dict[tuple[str, int], Cell] = {}

    _measures_to_create = []

    _processed_count = 0
    _error_cnt = 0

    _created_devices = 0
    _updated_devices = 0
    _created_operators = 0
    _created_cells = 0
    _updated_cells = 0
    _created_measures = 0
    _updated_measures = 0

    def handle(self, *args, **options):
        self.import_mqtt_2_db()

    @timer(mqtt_logger, True)
    def import_mqtt_2_db(self):
        try:
            with MongoClient(
                MQTT_MONGO_DB_URL, serverSelectionTimeoutMS=MQTT_CONN_TIMEOUT
            ) as client:
                db = client[MQTT_MONGO_DB_NAME]
                collection = db[MQTT_MONGO_DB_COLLECTION]

                cutoff_date = timezone.now() - MONGO_RETENTION_TTL
                date_filter_str = cutoff_date.strftime('%d.%m.%Y')

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

                        self._processed_count += 1
                        self._add_device_2_butch(validated_model)
                        self._add_operator_2_butch(validated_model)

                # Добавляем / обновляем хвосты:
                self._devices_butch_create(create_anyway=True)
                self._devices_butch_update(update_anyway=True)

                self._operators_butch_create(create_anyway=True)

                mqtt_logger.info(
                    'Импорт завершен. '
                    f'Обработано: {self._processed_count}.\n'
                    f'Создано: Devices={self._created_devices}, '
                    f'Operators={self._created_operators}, '
                    f'Cells={self._created_cells}, '
                    f'Measures={self._created_measures}.\n'
                    f'Обновлено: Devices={self._updated_devices}, '
                    f'Cells={self._updated_cells}, '
                    f'Measures={self._updated_measures}.\n'
                    f'Ошибок: {self._error_cnt}'
                )

        except errors.ServerSelectionTimeoutError:
            mqtt_logger.error('Таймаут подключения к MongoDB.')
        except KeyboardInterrupt:
            mqtt_logger.warning('Процесс прерван.')
        except Exception as e:
            mqtt_logger.exception(f'Неожиданная ошибка: {e}')

    def _process_document(self, doc: dict) -> Optional[ModemData]:
        try:
            data = doc.get('data', {})
            if not isinstance(data, dict):
                return None
            modem_raw = data.get('modem', {})
            if not isinstance(modem_raw, dict):
                return None
            return ModemData.model_validate(modem_raw)
        except ValidationError as e:
            self._log_error(e)
            return None
        except Exception as e:
            self._log_error(e)
            return None

    def _log_error(self, error: Exception):
        if self._error_cnt == 0:
            mqtt_logger.exception(f'Ошибка обработки: {str(error)}')
        else:
            mqtt_logger.debug(f'Ошибка обработки: {str(error)}', exc_info=True)
        self._error_cnt += 1

    def _add_device_2_butch(self, validated_model: ModemData):
        mac = validated_model.macaddress
        gps_lat = (
            validated_model.gps.lat
            if validated_model.gps else None
        )
        gps_lon = (
            validated_model.gps.lon
            if validated_model.gps else None
        )
        device = Device(
            mac_address=mac,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            sys_version=validated_model.sysversion,
            app_version=validated_model.appversion,
            last_seen=validated_model.event_datetime,

        )

        is_in_db = mac in self._devices_mac_in_db

        if is_in_db:
            self._devices_to_update[mac] = device
            self._devices_butch_update()
        else:
            self._devices_to_create[mac] = device
            self._devices_butch_create()

    def _devices_butch_create(self, create_anyway: bool = False):
        if not self._devices_to_create:
            return

        if len(self._devices_to_create) >= MQTT_DB_BATCH_SIZE or create_anyway:
            batch = list(self._devices_to_create.values())
            Device.objects.bulk_create(batch, ignore_conflicts=not DEBUG_MODE)

            new_macs = [d.mac_address for d in batch]
            self._devices_mac_in_db.update(new_macs)

            self._created_devices += len(batch)
            self._devices_to_create.clear()

    def _devices_butch_update(self, update_anyway: bool = False):
        if not self._devices_to_update:
            return

        if len(self._devices_to_update) >= MQTT_DB_BATCH_SIZE or update_anyway:
            macs_to_update = list(self._devices_to_update.keys())

            db_devices_qs = Device.objects.filter(
                mac_address__in=macs_to_update
            )

            db_devices_map = {d.mac_address: d for d in db_devices_qs}

            batch = []
            for mac, temp_device in self._devices_to_update.items():
                if mac in db_devices_map:
                    device_obj = db_devices_map[mac]
                    device_obj.gps_lat = temp_device.gps_lat
                    device_obj.gps_lon = temp_device.gps_lon
                    device_obj.sys_version = temp_device.sys_version
                    device_obj.app_version = temp_device.app_version
                    device_obj.last_seen = temp_device.last_seen
                    batch.append(device_obj)
                else:
                    Device.objects.get_or_create(
                        mac_address=temp_device.mac_address,
                        gps_lat=temp_device.gps_lat,
                        gps_lon=temp_device.gps_lon,
                        sys_version=temp_device.sys_version,
                        app_version=temp_device.app_version,
                        last_seen=temp_device.last_seen,

                    )

            if batch:
                Device.objects.bulk_update(
                    batch,
                    fields=[
                        'gps_lat',
                        'gps_lon',
                        'sys_version',
                        'app_version',
                        'last_seen',
                    ],
                )

            self._updated_devices += len(batch)
            self._devices_to_update.clear()

    def _add_operator_2_butch(self, validated_model: ModemData):
        if not validated_model.aops:
            return

        for aop in validated_model.aops:
            operator_name = (
                aop.cell.operator.operator_name
                or aop.cell.operator.operator_st_name
            )
            code = aop.cell.operator.operator_code

            operator = Operator(
                code=code,
                name=operator_name,

            )

            is_in_db = code in self._operators_code_in_db

            if not is_in_db:
                self._operators_to_create[code] = operator
                self._operators_butch_create()

    def _operators_butch_create(self, create_anyway: bool = False):
        if not self._operators_to_create:
            return

        if (
            len(self._operators_to_create) >= MQTT_DB_BATCH_SIZE
            or create_anyway
        ):
            batch = list(self._operators_to_create.values())
            Operator.objects.bulk_create(
                batch, ignore_conflicts=not DEBUG_MODE
            )

            new_codes = [d.code for d in batch]
            self._operators_code_in_db.update(new_codes)

            self._created_operators += len(batch)
            self._operators_to_create.clear()
