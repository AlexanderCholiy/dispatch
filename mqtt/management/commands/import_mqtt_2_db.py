from typing import Optional
from bson.objectid import ObjectId
from django.db.models import Q
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
    _cells_key_in_db: set[tuple[str, int]] = set(
        Cell.objects.values_list('operator__code', 'cell_id')
    )
    _cells_to_create: dict[tuple[str, int], Cell] = {}
    _cells_to_update: dict[tuple[str, int], Cell] = {}
    _operators_in_db: dict[str, Operator] = {
        op.code: op for op in Operator.objects.all()
    }

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
                        self._add_cell_2_butch(validated_model)

                # Добавляем / обновляем хвосты:
                self._devices_butch_create(create_anyway=True)
                self._devices_butch_update(update_anyway=True)

                self._operators_butch_create(create_anyway=True)

                self._cells_butch_create(create_anyway=True)
                self._cells_butch_update(update_anyway=True)

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
                        defaults={
                            'gps_lat': temp_device.gps_lat,
                            'gps_lon': temp_device.gps_lon,
                            'sys_version': temp_device.sys_version,
                            'app_version': temp_device.app_version,
                            'last_seen': temp_device.last_seen,
                        }
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

    def _add_cell_2_butch(self, validated_model: ModemData):
        if not validated_model.aops:
            return

        for aop in validated_model.aops:
            operator = aop.cell.operator
            cell = aop.cell

            cell_key = (operator.operator_code, cell.cellid)
            is_in_db = cell_key in self._cells_key_in_db

            operator_db = self._operators_in_db.get(operator.operator_code)

            if not operator_db:
                try:
                    operator_db = Operator.objects.get(
                        code=operator.operator_code
                    )
                    self._operators_in_db[operator.operator_code] = operator_db
                except Operator.DoesNotExist:
                    name = operator.operator_name or operator.operator_st_name
                    operator_db, _ = Operator.objects.get_or_create(
                        code=operator.operator_code,
                        defaults={'name': name}
                    )
                    self._operators_in_db[operator_db.code] = operator_db
                    self._operators_code_in_db.add(operator_db.code)
                    self._operators_to_create.pop(operator_db.code, None)

            cell_db = Cell(
                cell_id=cell.cellid,
                operator=operator_db,
                rat=cell.rat,
                freq=cell.freq,
                tac=cell.tac,
                lac=cell.lac,
                pci=cell.pci,
                psc=cell.psc,
                bsic=cell.bsic,
            )

            if is_in_db:
                self._cells_to_update[cell_key] = cell_db
                self._cells_butch_update()
            else:
                self._cells_to_create[cell_key] = cell_db
                self._cells_butch_create()

    def _cells_butch_create(self, create_anyway: bool = False):
        if not self._cells_to_create:
            return

        if len(self._cells_to_create) >= MQTT_DB_BATCH_SIZE or create_anyway:
            batch = list(self._cells_to_create.values())
            Cell.objects.bulk_create(batch, ignore_conflicts=not DEBUG_MODE)

            new_keys = [(c.operator.code, c.cell_id) for c in batch]
            self._cells_key_in_db.update(new_keys)

            self._created_cells += len(batch)
            self._cells_to_create.clear()

    def _cells_butch_update(self, update_anyway: bool = False):
        if not self._cells_to_update:
            return

        if len(self._cells_to_update) >= MQTT_DB_BATCH_SIZE or update_anyway:
            cells_to_update = list(self._cells_to_update.keys())

            conditions = []
            for op_code, cell_id in cells_to_update:
                conditions.append(
                    Q(operator__code=op_code) & Q(cell_id=cell_id)
                )

            combined_q = conditions[0]
            for condition in conditions[1:]:
                combined_q |= condition

            db_cells_qs = (
                Cell.objects.filter(combined_q).select_related('operator')
            )

            db_cells_map = {
                (c.operator.code, c.cell_id): c for c in db_cells_qs
            }

            batch = []
            for cell_key, temp_cell in self._cells_to_update.items():
                if cell_key in db_cells_map:
                    cell_obj = db_cells_map[cell_key]
                    cell_obj.operator = temp_cell.operator
                    cell_obj.rat = temp_cell.rat
                    cell_obj.freq = temp_cell.freq
                    cell_obj.tac = temp_cell.tac
                    cell_obj.lac = temp_cell.lac
                    cell_obj.pci = temp_cell.pci
                    cell_obj.psc = temp_cell.psc
                    cell_obj.bsic = temp_cell.bsic
                    batch.append(cell_obj)
                else:
                    op_code = temp_cell.operator.code
                    operator_db = self._operators_in_db.get(op_code)
                    if not operator_db:
                        try:
                            operator_db = Operator.objects.get(code=op_code)
                            self._operators_in_db[op_code] = operator_db
                        except Operator.DoesNotExist:
                            name = temp_cell.operator.name
                            operator_db, _ = Operator.objects.get_or_create(
                                code=op_code, defaults={'name': name}
                            )
                            self._operators_in_db[op_code] = operator_db
                            self._operators_code_in_db.add(op_code)
                            self._operators_to_create.pop(
                                operator_db.code, None
                            )

                    Cell.objects.get_or_create(
                        cell_id=temp_cell.cell_id,
                        operator=temp_cell.operator,
                        defaults={
                            'rat': temp_cell.rat,
                            'freq': temp_cell.freq,
                            'tac': temp_cell.tac,
                            'lac': temp_cell.lac,
                            'pci': temp_cell.pci,
                            'psc': temp_cell.psc,
                            'bsic': temp_cell.bsic,
                        }
                    )

            if batch:
                Cell.objects.bulk_update(
                    batch,
                    fields=[
                        'operator',
                        'rat',
                        'freq',
                        'tac',
                        'lac',
                        'pci',
                        'psc',
                        'bsic',
                    ],
                )

            self._updated_cells += len(batch)
            self._cells_to_update.clear()
