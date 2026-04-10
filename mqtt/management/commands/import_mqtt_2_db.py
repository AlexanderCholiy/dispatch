from datetime import datetime
from typing import Optional, TypedDict

from bson.objectid import ObjectId
from django.core.management.base import BaseCommand
from django.db.models import Q
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
from mqtt.models import Cell, CellMeasure, Device, Operator
from mqtt.shemas.modem_data import CellMeasure as CellMeasurePD
from mqtt.shemas.modem_data import ModemData


class CellMeasureValue(TypedDict):
    data: CellMeasurePD
    device: Device
    cell: Cell


class Command(BaseCommand):
    help = 'Импорт данных о радиопокрытии из MongoDB в БД'

    _devices_mac_in_db: set[str] = set(
        Device.objects.values_list('mac_address', flat=True)
    )
    _devices_to_create: dict[str, Device] = {}
    _devices_to_update: dict[str, Device] = {}

    # Ключ для сот: (operator_code, cell_id) -> объект Cell
    _cells_key_in_db: set[tuple[str, int]] = set(
        Cell.objects.values_list('operator__code', 'cell_id')
    )
    _cells_to_create: dict[tuple[str, int], Cell] = {}
    _cells_to_update: dict[tuple[str, int], Cell] = {}
    _operators_in_db: dict[str, Operator] = {
        op.code: op for op in Operator.objects.all()
    }

    # Ключ: (mac_address, cell_key, measure_data_dict)
    _raw_measures: list[tuple[str, tuple[str, int], CellMeasurePD]] = []

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

    @timer(mqtt_logger, False)
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
                    desc='Добавление (обновление) Device, Operator, Cell',
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
                        self._add_cell_2_butch(validated_model)

                # Добавляем / обновляем хвосты:
                self._devices_butch_create(create_anyway=True)
                self._devices_butch_update(update_anyway=True)

                self._cells_butch_create(create_anyway=True)
                self._cells_butch_update(update_anyway=True)

                # Сохраняем измерения после того как Devices и Cells сохранены:
                self._cells_measures_save()

                mqtt_logger.info(
                    f'Обработано: {self._processed_count}. '
                    f'Ошибок: {self._error_cnt}\n'
                    f'Создано: Devices={self._created_devices}, '
                    f'Operators={self._created_operators}, '
                    f'Cells={self._created_cells}, '
                    f'Measures={self._created_measures}.\n'
                    f'Обновлено: Devices={self._updated_devices}, '
                    f'Cells={self._updated_cells}, '
                    f'Measures={self._updated_measures}.'
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
                device_obj = db_devices_map.get(mac)
                has_changes = (
                    device_obj.gps_lat != temp_device.gps_lat
                    or device_obj.gps_lon != temp_device.gps_lon
                    or device_obj.sys_version != temp_device.sys_version
                    or device_obj.app_version != temp_device.app_version
                    or device_obj.last_seen != temp_device.last_seen
                ) if device_obj else True

                if device_obj and has_changes:
                    device_obj.gps_lat = temp_device.gps_lat
                    device_obj.gps_lon = temp_device.gps_lon
                    device_obj.sys_version = temp_device.sys_version
                    device_obj.app_version = temp_device.app_version
                    device_obj.last_seen = temp_device.last_seen
                    batch.append(device_obj)
                elif not device_obj:
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

    def _add_cell_2_butch(self, validated_model: ModemData):
        if not validated_model.aops:
            return

        for aop in validated_model.aops:
            operator = aop.cell.operator
            cell = aop.cell

            cell_key = (operator.operator_code, cell.cellid)
            is_in_db = cell_key in self._cells_key_in_db

            operator_db = self._operators_in_db.get(operator.operator_code)
            op_name = operator.operator_name or operator.operator_st_name

            if not operator_db:
                operator_db, op_creat = Operator.objects.get_or_create(
                    code=operator.operator_code,
                    defaults={'name': op_name}
                )
                self._operators_in_db[operator_db.code] = operator_db
                if op_creat:
                    self._created_operators += 1
            else:
                if not operator_db.name and op_name:
                    operator_db.name = op_name
                    operator_db.save(update_fields=['name'])
                    self._operators_in_db[operator_db.code] = operator_db

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

            self._raw_measures.append(
                (validated_model.macaddress, cell_key, aop)
            )

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
                cell_obj = db_cells_map.get(cell_key)
                has_changes = (
                    cell_obj.operator != temp_cell.operator
                    or cell_obj.rat != temp_cell.rat
                    or cell_obj.freq != temp_cell.freq
                    or cell_obj.tac != temp_cell.tac
                    or cell_obj.lac != temp_cell.lac
                    or cell_obj.pci != temp_cell.pci
                    or cell_obj.psc != temp_cell.psc
                    or cell_obj.bsic != temp_cell.bsic
                ) if cell_obj else True

                if cell_obj and has_changes:
                    cell_obj.operator = temp_cell.operator  # Оператор уже в БД
                    cell_obj.rat = temp_cell.rat
                    cell_obj.freq = temp_cell.freq
                    cell_obj.tac = temp_cell.tac
                    cell_obj.lac = temp_cell.lac
                    cell_obj.pci = temp_cell.pci
                    cell_obj.psc = temp_cell.psc
                    cell_obj.bsic = temp_cell.bsic
                    batch.append(cell_obj)
                elif not cell_obj:
                    op_code = temp_cell.operator.code
                    operator_db = self._operators_in_db.get(op_code)
                    op_name = temp_cell.operator.name
                    if not operator_db:
                        operator_db, op_creat = Operator.objects.get_or_create(
                            code=op_code, defaults={'name': op_name}
                        )
                        self._operators_in_db[op_code] = operator_db
                        if op_creat:
                            self._created_operators += 1
                    else:
                        if not operator_db.name and op_name:
                            operator_db.name = op_name
                            operator_db.save(update_fields=['name'])
                            self._operators_in_db[op_code] = operator_db

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

    def _cells_measures_save(self):
        if not self._raw_measures:
            return

        needed_macs = set()
        needed_cell_keys = set()
        for mac, cell_key, _ in self._raw_measures:
            needed_macs.add(mac)
            needed_cell_keys.add(cell_key)

        total_unique_macs = len(needed_macs)
        total_unique_cells = len(needed_cell_keys)
        total_raw_records = len(self._raw_measures)
        total_search_keys = 0

        devices_map: dict[str, Device] = {}
        mac_list = list(needed_macs)

        with tqdm(
            total=total_unique_macs,
            desc='Загрузка Device из БД',
            colour='cyan',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for i in range(0, len(mac_list), MQTT_DB_BATCH_SIZE):
                batch = mac_list[i:i + MQTT_DB_BATCH_SIZE]
                chunk_qs = Device.objects.filter(mac_address__in=batch)
                count_loaded = 0
                for d in chunk_qs:
                    devices_map[d.mac_address] = d
                    count_loaded += 1

                pbar.update(count_loaded)

        cells_map: dict[tuple[str, int], Cell] = {}
        cell_key_list = list(needed_cell_keys)

        with tqdm(
            total=total_unique_cells,
            desc='Загрузка Cell из БД',
            colour='cyan',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for i in range(0, len(cell_key_list), MQTT_DB_BATCH_SIZE):
                chunk_keys = cell_key_list[i:i + MQTT_DB_BATCH_SIZE]
                combined_q_chunk = Q()
                for op_code, cell_id in chunk_keys:
                    combined_q_chunk |= Q(
                        operator__code=op_code, cell_id=cell_id
                    )

                chunk_qs = (
                    Cell.objects.filter(combined_q_chunk)
                    .select_related('operator')
                )
                count_loaded = 0
                for c in chunk_qs:
                    cells_map[(c.operator.code, c.cell_id)] = c
                    count_loaded += 1

                pbar.update(count_loaded)

        temp_data_map: dict[tuple[int, int, datetime], CellMeasureValue] = {}

        with tqdm(
            total=total_raw_records,
            desc='Формирование маппинга CellMeasure',
            colour='blue',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for mac, cell_key, data in self._raw_measures:
                device_obj = devices_map.get(mac)
                cell_obj = cells_map.get(cell_key)

                if not device_obj or not cell_obj:
                    missing = []
                    if not device_obj:
                        missing.append(f'Device (mac={mac})')
                    if not cell_obj:
                        op_code, cell_id = cell_key
                        missing.append(f'Cell (id={cell_id}, op={op_code})')
                    mqtt_logger.warning(
                        f'Данные по {", ".join(missing)} не найдены.'
                    )
                    pbar.update(1)
                    continue

                measure_key = (
                    device_obj.pk, cell_obj.pk, device_obj.last_seen
                )
                temp_data_map[measure_key] = {
                    'data': data,
                    'device': device_obj,
                    'cell': cell_obj,
                }
                pbar.update(1)

        keys_to_process = list(temp_data_map.keys())
        total_search_keys = len(keys_to_process)
        found_measures: list[CellMeasure] = []

        with tqdm(
            total=total_search_keys,
            desc='Поиск существующих CellMeasure в БД',
            colour='blue',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for i in range(0, len(keys_to_process), MQTT_DB_BATCH_SIZE):
                chunk_keys = keys_to_process[i:i + MQTT_DB_BATCH_SIZE]
                q_list = [
                    Q(device_id=k[0], cell_id=k[1], event_datetime=k[2])
                    for k in chunk_keys
                ]
                combined_q_chunk = q_list[0]
                for q in q_list[1:]:
                    combined_q_chunk |= q

                qs = CellMeasure.objects.filter(combined_q_chunk)
                count_found = 0
                for m in qs:
                    found_measures.append(m)
                    count_found += 1

                pbar.update(count_found)

        existing_measures_map: dict[
            tuple[int, int, datetime], CellMeasure
        ] = {}
        with tqdm(
            total=len(found_measures),
            desc='Формирование кэша существующих CellMeasure',
            colour='blue',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for m in found_measures:
                key = (m.device_id, m.cell_id, m.event_datetime)
                existing_measures_map[key] = m
                pbar.update(1)

        to_create: list[CellMeasure] = []
        to_update: list[CellMeasure] = []

        with tqdm(
            total=len(temp_data_map),
            desc='Распределение CellMeasure: CREATE vs UPDATE',
            colour='red',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for key, item in temp_data_map.items():
                data = item['data']
                device_obj = item['device']
                cell_obj = item['cell']
                existing_obj = existing_measures_map.get(key)

                has_changes = (
                    existing_obj.device != device_obj
                    or existing_obj.cell != cell_obj
                    or existing_obj.index != data.index
                    or existing_obj.cba != data.cba
                    or existing_obj.event_datetime != device_obj.last_seen
                    or existing_obj.rsrp != data.rsrp
                    or existing_obj.rsrq != data.rsrq
                    or existing_obj.rscp != data.rscp
                    or existing_obj.ecno != data.ecno
                    or existing_obj.rssi != data.rssi
                    or existing_obj.rxlev != data.rxlev
                    or existing_obj.c1 != data.c1
                ) if existing_obj else True

                if existing_obj and has_changes:
                    to_update.append(existing_obj)
                elif not existing_obj:
                    new_measure = CellMeasure(
                        device=device_obj,
                        cell=cell_obj,
                        index=data.index,
                        cba=data.cba,
                        event_datetime=device_obj.last_seen,
                        rsrp=data.rsrp,
                        rsrq=data.rsrq,
                        rscp=data.rscp,
                        ecno=data.ecno,
                        rssi=data.rssi,
                        rxlev=data.rxlev,
                        c1=data.c1,
                    )
                    to_create.append(new_measure)

                pbar.update(1)

        with tqdm(
            total=len(to_update),
            desc='Сохранение обновлений (CellMeasure)',
            colour='green',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for i in range(0, len(to_update), MQTT_DB_BATCH_SIZE):
                batch = to_update[i:i + MQTT_DB_BATCH_SIZE]
                if batch:
                    CellMeasure.objects.bulk_update(
                        batch,
                        fields=[
                            'index', 'cba', 'rsrp',
                            'rsrq', 'rscp', 'ecno',
                            'rssi', 'rxlev', 'c1',
                        ]
                    )
                    self._updated_measures += len(batch)
                pbar.update(len(batch))

        with tqdm(
            total=len(to_create),
            desc='Сохранение новых записей (CellMeasure)',
            colour='green',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for i in range(0, len(to_create), MQTT_DB_BATCH_SIZE):
                batch = to_create[i:i + MQTT_DB_BATCH_SIZE]
                if batch:
                    CellMeasure.objects.bulk_create(
                        batch, ignore_conflicts=not DEBUG_MODE
                    )
                    self._created_measures += len(batch)
                pbar.update(len(batch))
