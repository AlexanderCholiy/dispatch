import json
from http import HTTPStatus
from types import NoneType
from typing import Generator, Iterable
from numpy import nan

import pandas as pd
import requests
from django.db import transaction, connections
from django.db.models import Q

from core.constants import TS_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.wraps import timer

from .constants import (
    # AVR_FILE,
    # BASE_STATIONS_FILE,
    COLUMNS_TO_KEEP_AVR_REPORT,
    COLUMNS_TO_KEEP_BS_OPERATORS_REPORT,
    COLUMNS_TO_KEEP_POLES_TL,
    DB_CHUNK_UPDATE,
    # POLES_FILE,
    TS_AVR_REPORT_URL,
    TS_BS_REPORT_URL,
    TS_POLES_TL_URL,
    UNDEFINED_CASE,
    UNDEFINED_EMAILS,
    UNDEFINED_ID,
)
from .models import (
    AVRContractor,
    BaseStation,
    BaseStationOperator,
    ContractorEmail,
    ContractorPhone,
    Pole,
    PoleContractorEmail,
    PoleContractorPhone,
    Region,
)
from .validators import SocialValidators

ts_api_logger = LoggerFactory(__name__, TS_LOG_ROTATING_FILE).get_logger()


class Api(SocialValidators):
    """Загрузка данных из TS и добавление их в БД"""

    @staticmethod
    @timer(ts_api_logger)
    def download_json(
        self, json_file_path: str, url: str, chunk_size: int = 1000
    ):
        response = requests.get(url, stream=True)

        if response.status_code == HTTPStatus.OK:
            loaded_size = 0
            ts_api_logger.debug(f'Загрузка данных из "{url}"')

            with open(json_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        loaded_size += len(chunk)
                        f.write(chunk)

        else:
            ts_api_logger.critical(f'Ошибка при загрузки данных из "{url}"')

    def json_2_df(
        self, json_file_path: str, columns_to_keep: list[str]
    ) -> pd.DataFrame:
        with open(json_file_path, 'r', encoding='utf-8-sig') as file:
            data = json.load(file)
            df = (
                pd.DataFrame(data)[columns_to_keep]
                .drop_duplicates()
                .reset_index(drop=True)
            )
        df.replace('', None, inplace=True)
        df.replace(nan, None, inplace=True)
        return df

    def chunked(
        self, iterable: Iterable, chunk_size: int = 100
    ) -> Generator[list, None, None]:
        """Делит итерируемый объект на части заданного размера."""
        items = list(iterable)
        for i in range(0, len(items), chunk_size):
            yield items[i:i + chunk_size]

    def get_ts_poles(self) -> pd.DataFrame:
        columns_quoted = ', '.join(
            f'"{col}"' if col != 'RegionRu' else '"Регион ru" AS "RegionRu"'
            for col in COLUMNS_TO_KEEP_POLES_TL
        )
        query = f'SELECT {columns_quoted} FROM "Таблица опор";'

        with connections['ts'].cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()

        return pd.DataFrame.from_records(data, columns=columns)

    def _is_pole_changed(
        self, pole_obj: Pole, row: dict, region_obj: Region
    ) -> bool:
        return (
            pole_obj.pole != row['Шифр']
            or pole_obj.bs_name != row['Имя БС']
            or pole_obj.pole_status != (row['Статус опоры'] or None)
            or pole_obj.pole_latitude != (row['Широта'] or None)
            or pole_obj.pole_longtitude != (row['Долгота'] or None)
            or pole_obj.pole_height != (row['Высота опоры'] or None)
            or pole_obj.address != (row['Адрес'] or None)
            or pole_obj.infrastructure_company != (
                row['Инфраструктурная компания'] or None
            )
            or pole_obj.anchor_operator != (row['Якорный оператор'] or None)
            or pole_obj.region_id != region_obj.id
        )

    @transaction.atomic
    def update_poles(self, update_json: bool = True):
        # if update_json or not os.path.exists(POLES_FILE):
        #     self.download_json(POLES_FILE, TS_POLES_TL_URL)

        # poles = self.json_2_df(POLES_FILE, COLUMNS_TO_KEEP_POLES_TL)
        poles = self.get_ts_poles()

        poles['SiteId'] = poles['SiteId'].astype(int)
        poles['Широта'] = poles['Широта'].astype(float)
        poles['Долгота'] = poles['Долгота'].astype(float)
        poles['Высота опоры'] = poles['Высота опоры'].astype(float)
        total = len(poles)

        # Удаляем не актуальные записи:
        new_site_ids: set[int] = set(poles['SiteId'])
        existing_site_ids: set[int] = set(
            Pole.objects.values_list('site_id', flat=True)
        )
        poles_2_delete = (
            existing_site_ids
            - new_site_ids
            - {UNDEFINED_ID}
        )
        if poles_2_delete:
            deleted_poles = 0
            for chunk in self.chunked(poles_2_delete, DB_CHUNK_UPDATE):
                del_poles_i, _ = (
                    Pole.objects.filter(site_id__in=chunk).delete()
                )
                deleted_poles += del_poles_i
            ts_api_logger.debug(
                'Pole удалены: '
                f'{deleted_poles} из {len(poles_2_delete)}'
            )

        # Добавляем опору по умолчанию:
        Pole.add_default_value()

        poles_cache = {
            p.site_id: p for p in Pole.objects.select_related('region')
        }
        regions_cache = {r.region_en: r for r in Region.objects.all()}

        bulk_poles_to_create = []
        bulk_regions_to_create = []
        poles_to_update = []

        # Обновляем актуальные записи:
        find_unvalid_values = False

        for index, row in poles.iterrows():
            PrettyPrint.progress_bar_debug(index, total, 'Обновление Pole:')

            site_id = row['SiteId']
            pole = row['Шифр']
            bs_name = row['Имя БС']
            pole_status = row['Статус опоры'] or None
            pole_latitude = row['Широта'] or None
            pole_longtitude = row['Долгота'] or None
            pole_height = row['Высота опоры'] or None
            address = row['Адрес'] or None
            infrastructure_company = row['Инфраструктурная компания'] or None
            anchor_operator = row['Якорный оператор'] or None
            region_en = row['Регион'] or None
            region_ru = row['RegionRu'] or None

            if (
                not isinstance(site_id, int)
                or not isinstance(pole, str)
                or not isinstance(bs_name, str)
                or not isinstance(pole_status, (str, NoneType))
                or not isinstance(pole_latitude, (float, NoneType))
                or not isinstance(pole_longtitude, (float, NoneType))
                or not isinstance(pole_height, (float, NoneType))
                or not isinstance(address, (str, NoneType))
                or not isinstance(infrastructure_company, (str, NoneType))
                or not isinstance(anchor_operator, (str, NoneType))
                or not isinstance(region_en, str)
                or not isinstance(region_ru, (str, NoneType))
            ):
                find_unvalid_values = True
                continue

            region_obj = regions_cache.get(region_en)
            if not region_obj:
                region_obj = Region(region_en=region_en, region_ru=region_ru)
                regions_cache[region_en] = region_obj
                bulk_regions_to_create.append(region_obj)

            pole_obj = poles_cache.get(site_id)
            if pole_obj:
                if self._is_pole_changed(pole_obj, row, region_obj):
                    pole_obj.pole = pole
                    pole_obj.bs_name = bs_name
                    pole_obj.pole_status = pole_status
                    pole_obj.pole_latitude = pole_latitude
                    pole_obj.pole_longtitude = pole_longtitude
                    pole_obj.pole_height = pole_height
                    pole_obj.region = region_obj
                    pole_obj.address = address
                    pole_obj.infrastructure_company = infrastructure_company
                    pole_obj.anchor_operator = anchor_operator

                    poles_to_update.append(pole_obj)
            else:
                bulk_poles_to_create.append(
                    Pole(
                        site_id=site_id,
                        pole=pole,
                        bs_name=bs_name,
                        pole_status=pole_status,
                        pole_latitude=pole_latitude,
                        pole_longtitude=pole_longtitude,
                        pole_height=pole_height,
                        region=region_obj,
                        address=address,
                        infrastructure_company=infrastructure_company,
                        anchor_operator=anchor_operator,
                    )
                )

        if find_unvalid_values:
            ts_api_logger.warning(f'Проверьте данные в {TS_POLES_TL_URL}')

        if bulk_regions_to_create:
            new_created_regions = Region.objects.bulk_create(
                bulk_regions_to_create,
                ignore_conflicts=True, batch_size=DB_CHUNK_UPDATE
            )
            created_regions = {r.region_en: r for r in new_created_regions}
            regions_cache.update(created_regions)
            ts_api_logger.debug(
                'Region добавлены: '
                f'{len(new_created_regions)} из {len(bulk_regions_to_create)}'
            )

        for p in bulk_poles_to_create:
            p: Pole
            p.region = regions_cache[p.region.region_en]

        if bulk_poles_to_create:
            created_poles = Pole.objects.bulk_create(
                bulk_poles_to_create,
                ignore_conflicts=True,
                batch_size=DB_CHUNK_UPDATE
            )
            ts_api_logger.debug(
                'Pole добавлены: '
                f'{len(created_poles)} из {len(bulk_poles_to_create)}'
            )

        if poles_to_update:
            updated_poles = Pole.objects.bulk_update(
                poles_to_update,
                fields=[
                    'pole',
                    'bs_name',
                    'pole_status',
                    'pole_latitude',
                    'pole_longtitude',
                    'pole_height',
                    'region',
                    'address',
                    'infrastructure_company',
                    'anchor_operator',
                ],
                batch_size=DB_CHUNK_UPDATE
            )
            ts_api_logger.debug(
                f'Pole обновлены: {updated_poles} из {len(poles_to_update)}'
            )

    def get_ts_avr(self) -> pd.DataFrame:
        email_col = (
            '"2_Контактные данные подрядчика Email" '
            'AS "Контактные данные подрядчика Email"'
        )
        phone_col = (
            '"3_Контактные данные подрядчика Тел" '
            'AS "Контактные данные подрядчика Телефон"'
        )

        columns_quoted = ', '.join(
            (
                email_col
                if col == 'Контактные данные подрядчика Email'
                else phone_col
                if col == 'Контактные данные подрядчика Телефон'
                else f'"{col}"'
            )
            for col in COLUMNS_TO_KEEP_AVR_REPORT
        )
        query = f'SELECT {columns_quoted} FROM "АВР";'

        with connections['ts'].cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()

        return pd.DataFrame.from_records(data, columns=columns)

    def update_avr(self, update_json: bool = True):
        """
        Обновление подрядчиков по АВР.

        Если для опоры отсутсвует подрядчик тогда берем по умолчанию.
        Если для подрядчика нет Email, тогда ничего не выставляем.
        """
        # if update_json or not os.path.exists(AVR_FILE):
        #     self.download_json(AVR_FILE, TS_AVR_REPORT_URL)

        # avr = self.json_2_df(AVR_FILE, COLUMNS_TO_KEEP_AVR_REPORT)
        avr = self.get_ts_avr()
        total = len(avr)

        contractors_cache = {
            c.contractor_name: c for c in AVRContractor.objects.all()
        }
        email_objs = {o.email: o for o in ContractorEmail.objects.all()}
        phone_objs = {o.phone: o for o in ContractorPhone.objects.all()}

        # Удаляем не актуальные записи
        new_contractors: set[str] = set(avr['Подрядчик'].dropna())
        existing_contractors: set[str] = set(contractors_cache.keys())
        contractors_to_delete = (
            existing_contractors - new_contractors - {UNDEFINED_CASE}
        )

        if contractors_to_delete:
            deleted_avr, _ = AVRContractor.objects.filter(
                contractor_name__in=contractors_to_delete
            ).delete()
            for name in contractors_to_delete:
                contractors_cache.pop(name, None)
            ts_api_logger.debug(
                'AVRContractor удалены: '
                f'{deleted_avr} из {len(contractors_to_delete)}'
            )

        # Дефолтный подрядчик и дефолтная опора
        with transaction.atomic():
            default_contractor, _ = AVRContractor.objects.update_or_create(
                contractor_name=UNDEFINED_CASE,
                defaults={'is_excluded_from_contract': False}
            )
            contractors_cache[UNDEFINED_CASE] = default_contractor

            default_pole = Pole.add_default_value()
            if default_pole.avr_contractor_id != default_contractor.id:
                default_pole.avr_contractor = default_contractor
                default_pole.save(update_fields=['avr_contractor'])

            # Дефолтные email для дефолтной опоры
            for email in UNDEFINED_EMAILS:
                obj, _ = ContractorEmail.objects.get_or_create(email=email)

                PoleContractorEmail.objects.get_or_create(
                    contractor=default_contractor,
                    pole=default_pole,
                    email=obj
                )

        # Кеш всех опор
        poles_cache: dict[str, Pole] = {p.pole: p for p in Pole.objects.all()}

        # Кэш существующих email/phone связей
        email_cache = {}
        for link in PoleContractorEmail.objects.select_related('email'):
            email_cache.setdefault(
                (link.contractor_id, link.pole_id), set()
            ).add(link.email.email)

        phone_cache = {}
        for link in PoleContractorPhone.objects.select_related('phone'):
            phone_cache.setdefault(
                (link.contractor_id, link.pole_id), set()
            ).add(link.phone.phone)

        updated_poles = []
        poles_in_avr = set()
        email_and_phones_pairs_to_delete = set()

        find_unvalid_values = False

        for index, row in avr.iterrows():
            PrettyPrint.progress_bar_info(
                index, total,
                (
                    'Обновление AVRContractor, ContractorEmail, '
                    'ContractorPhone и связей с Pole:'
                )
            )

            try:
                pole_number = row['Шифр опоры']
                contractor_name = row.get('Подрядчик')
                contractor_emails = row.get(
                    'Контактные данные подрядчика Email')
                contractor_phones = row.get(
                    'Контактные данные подрядчика Телефон')
                is_excluded_val = str(
                    row.get('Исключен из договора') or ''
                ).strip().lower()
                is_excluded_from_contract = is_excluded_val not in (
                    'нет', 'no', ''
                )

                # Проверка типов
                if not isinstance(pole_number, str):
                    find_unvalid_values = True
                    continue

                # Подрядчик
                if contractor_name:
                    contractor = contractors_cache.get(contractor_name)

                    if contractor:
                        if (
                            contractor.is_excluded_from_contract != (
                                is_excluded_from_contract
                            )
                        ):
                            contractor.is_excluded_from_contract = (
                                is_excluded_from_contract
                            )
                            contractor.save(
                                update_fields=['is_excluded_from_contract']
                            )
                    else:
                        contractor = AVRContractor.objects.create(
                            contractor_name=contractor_name,
                            is_excluded_from_contract=is_excluded_from_contract
                        )
                        contractors_cache[contractor_name] = contractor
                else:
                    # Не актуальные записи обновим потом
                    contractor = default_contractor

                # Опора
                pole = poles_cache.get(pole_number, default_pole)
                if pole.avr_contractor_id != contractor.id:
                    pole.avr_contractor = contractor
                    updated_poles.append(pole)

                poles_in_avr.add(pole.pole)

                # Старые связи нужно удалить, если contractor != текущий
                email_and_phones_pairs_to_delete.add((pole.id, contractor.id))

                key = (contractor.pk, pole.pk)

                # Email
                if contractor_emails:
                    valid_emails, _ = self.split_and_validate_emails(
                        contractor_emails
                    )
                else:
                    valid_emails = UNDEFINED_EMAILS if (
                        contractor == default_contractor
                    ) else []

                new_emails = set(valid_emails)
                old_emails = email_cache.get(key, set())
                email_cache[key] = new_emails

                # Удаляем устаревшие связи подрядчик - email
                to_remove = old_emails - new_emails
                if to_remove:
                    PoleContractorEmail.objects.filter(
                        contractor=contractor,
                        pole=pole,
                        email__email__in=to_remove
                    ).delete()

                # Добавляем новые
                for email in new_emails - old_emails:
                    email_obj = email_objs.get(email)
                    if not email_obj:
                        email_obj = ContractorEmail.objects.create(email=email)
                        email_objs[email] = email_obj

                    PoleContractorEmail.objects.get_or_create(
                        contractor=contractor,
                        pole=pole,
                        email=email_obj
                    )

                # Phone
                if contractor_phones:
                    valid_phones, _ = self.split_and_validate_phones(
                        contractor_phones
                    )
                else:
                    valid_phones = []

                new_phones = set(valid_phones)
                old_phones = phone_cache.get(key, set())
                phone_cache[key] = new_phones

                # Удаляем устаревшие связи подрядчик - телефон
                to_remove_phones = old_phones - new_phones
                if to_remove_phones:
                    PoleContractorPhone.objects.filter(
                        contractor=contractor,
                        pole=pole,
                        phone__phone__in=to_remove_phones
                    ).delete()

                # Добавляем новые
                for phone in new_phones - old_phones:
                    phone_obj = phone_objs.get(phone)
                    if not phone_obj:
                        phone_obj = ContractorPhone.objects.create(phone=phone)
                        phone_objs[phone] = phone_obj

                    PoleContractorPhone.objects.get_or_create(
                        contractor=contractor,
                        pole=pole,
                        phone=phone_obj
                    )

            except Exception:
                ts_api_logger.debug(f'Проверьте данные: {row}')
                find_unvalid_values = True

        if find_unvalid_values:
            ts_api_logger.warning(f'Проверьте данные в {TS_AVR_REPORT_URL}')

        if updated_poles:
            success_updated_poles = Pole.objects.bulk_update(
                updated_poles, ['avr_contractor'], batch_size=DB_CHUNK_UPDATE
            )
            ts_api_logger.debug(
                'Pole обновлены: '
                f'{success_updated_poles} из {len(updated_poles)}'
            )

        # Удаляем все устаревшие email/phone связи:
        pairs_list = list(email_and_phones_pairs_to_delete)
        chunks = list(self.chunked(pairs_list, DB_CHUNK_UPDATE))
        total = len(chunks)
        for index, batch in enumerate(chunks):
            PrettyPrint.progress_bar_success(
                index, total,
                (
                    'Удаление устаревших связей PoleContractorEmail и '
                    'PoleContractorPhone:'
                )
            )
            q = Q()
            for pole_id, contractor_id in batch:
                q |= Q(pole_id=pole_id) & ~Q(contractor_id=contractor_id)

            PoleContractorEmail.objects.filter(q).delete()
            PoleContractorPhone.objects.filter(q).delete()

        # Удаление связей опора - подрядчик, когда опора отсутсвует в выгрузке:
        poles_to_reset = Pole.objects.filter(
            pole__in=set(poles_cache.keys()) - poles_in_avr
        )

        if poles_to_reset:
            poles_to_reset.update(avr_contractor=default_contractor)
            PoleContractorEmail.objects.filter(
                pole__in=poles_to_reset
            ).delete()
            PoleContractorPhone.objects.filter(
                pole__in=poles_to_reset
            ).delete()

            default_email_objs = {
                email: ContractorEmail.objects.get_or_create(email=email)[0]
                for email in UNDEFINED_EMAILS
            }

            bulk_links = []
            total = len(poles_to_reset)

            for index, pole in enumerate(poles_to_reset):
                PrettyPrint.progress_bar_warning(
                    index, total,
                    (
                        'Назначение дефолтного подрядчика и '
                        'PoleContractorEmail для отсутствующих Pole в '
                        'выгрузке:'
                    )
                )
                for email_obj in default_email_objs.values():
                    bulk_links.append(
                        PoleContractorEmail(
                            contractor=default_contractor,
                            pole=pole,
                            email=email_obj
                        )
                    )

            PoleContractorEmail.objects.bulk_create(
                bulk_links, ignore_conflicts=True, batch_size=DB_CHUNK_UPDATE
            )

    def get_ts_bs(self) -> pd.DataFrame:
        columns_quoted = ', '.join(
            f'"{col}"' for col in COLUMNS_TO_KEEP_BS_OPERATORS_REPORT
        )
        query = f'SELECT {columns_quoted} FROM "EI.Размещённые арендаторы";'

        with connections['ts'].cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()

        return pd.DataFrame.from_records(data, columns=columns)

    @transaction.atomic
    def update_base_stations(self, update_json: bool = True):
        # if update_json or not os.path.exists(BASE_STATIONS_FILE):
        #     self.download_json(BASE_STATIONS_FILE, TS_BS_REPORT_URL)

        # base_stations = self.json_2_df(
        #     BASE_STATIONS_FILE, COLUMNS_TO_KEEP_BS_OPERATORS_REPORT
        # )
        base_stations = self.get_ts_bs()
        total = len(base_stations)

        # Удаляем не актуальные записи:
        new_bs_combinations = set(
            zip(
                base_stations['Шифр опоры'],
                base_stations['Имя БС/Оборудование']
            )
        )
        existing_bs_combinations = set(
            BaseStation.objects.values_list('pole__pole', 'bs_name')
        )
        combinations_bs_to_delete = (
            existing_bs_combinations - new_bs_combinations
        )

        if combinations_bs_to_delete:
            deleted_count = 0
            for chunk in self.chunked(
                combinations_bs_to_delete, chunk_size=DB_CHUNK_UPDATE
            ):
                query = Q()
                for pole_val, bs_val in chunk:
                    query |= Q(pole__pole=pole_val, bs_name=bs_val)

                deleted_count_i, _ = BaseStation.objects.filter(query).delete()

                deleted_count += deleted_count_i

            ts_api_logger.debug(
                'BaseStation удалены: '
                f'{deleted_count} из {len(combinations_bs_to_delete)}'
            )

        new_operators_combinations = set(
            zip(
                base_stations['Оператор'], base_stations['Группа операторов']
            )
        )
        existing_operators_combinations = set(
            BaseStationOperator.objects.values_list(
                'operator_name', 'operator_group'
            )
        )
        combinations_operators_to_delete = (
            existing_operators_combinations - new_operators_combinations
        )

        if combinations_operators_to_delete:
            deleted_count = 0
            for chunk in self.chunked(
                combinations_operators_to_delete, chunk_size=DB_CHUNK_UPDATE
            ):
                query = Q()
                for op_name, op_group in chunk:
                    query |= Q(operator_name=op_name, operator_group=op_group)
                deleted_count_i, _ = (
                    BaseStationOperator.objects.filter(query).delete()
                )
                deleted_count += deleted_count_i
            ts_api_logger.debug(
                'BaseStationOperator удалены: '
                f'{deleted_count} из {len(combinations_operators_to_delete)}'
            )

        # Кешируем все существующие опоры и операторов:
        poles = {p.pole: p for p in Pole.objects.all()}
        bs_cache: dict[tuple[str, int], BaseStation] = {
            (b.bs_name, b.pole_id): b
            for b in BaseStation.objects.select_related('pole')
        }
        operators_cache: dict[tuple[str, str], BaseStationOperator] = {
            (o.operator_name, o.operator_group): o
            for o in BaseStationOperator.objects.all()
        }

        bulk_bs_to_create = []
        bulk_operators_to_create = []
        relations_to_set = []

        find_unvalid_values = False

        for index, row in base_stations.iterrows():
            PrettyPrint.progress_bar_error(
                index, total, 'Обновление BaseStation и BaseStationOperator:'
            )

            pole_number = row['Шифр опоры']
            bs_name = row['Имя БС/Оборудование']
            operator_name = row['Оператор']
            operator_group = row['Группа операторов']

            if isinstance(bs_name, NoneType):
                continue

            if (
                not isinstance(pole_number, str)
                or not isinstance(bs_name, str)
                or not isinstance(operator_name, str)
                or not isinstance(operator_group, (str, NoneType))
            ):
                find_unvalid_values = True
                continue

            pole = poles.get(pole_number)
            if not pole:
                continue

            bs_key = (bs_name, pole.id)
            base_station = bs_cache.get(bs_key)
            if not base_station:
                base_station = BaseStation(bs_name=bs_name, pole=pole)
                bs_cache[bs_key] = base_station
                bulk_bs_to_create.append(base_station)

            relations_to_set.append(
                ((bs_name, pole.id), (operator_name, operator_group))
            )

            op_key = (operator_name, operator_group)
            if op_key not in operators_cache:
                operators_cache[op_key] = BaseStationOperator(
                    operator_name=operator_name,
                    operator_group=operator_group
                )
                bulk_operators_to_create.append(operators_cache[op_key])

        if find_unvalid_values:
            ts_api_logger.warning(f'Проверьте данные в {TS_BS_REPORT_URL}')

        if bulk_operators_to_create:
            new_operators = BaseStationOperator.objects.bulk_create(
                bulk_operators_to_create,
                ignore_conflicts=True,
                batch_size=DB_CHUNK_UPDATE
            )
            operators_cache = {
                (o.operator_name, o.operator_group): o
                for o in BaseStationOperator.objects.all()
            }
            ts_api_logger.debug(
                'BaseStationOperator добавлены: '
                f'{len(new_operators)} из {len(bulk_operators_to_create)}'
            )

        if bulk_bs_to_create:
            new_bs = BaseStation.objects.bulk_create(
                bulk_bs_to_create,
                ignore_conflicts=True,
                batch_size=DB_CHUNK_UPDATE
            )
            bs_cache = {
                (b.bs_name, b.pole_id): b
                for b in BaseStation.objects.select_related('pole')
            }
            ts_api_logger.debug(
                'BaseStationOperator добавлены: '
                f'{len(new_bs)} из {len(bulk_bs_to_create)}'
            )

        bs_2_operators: dict[tuple[str, int], list[BaseStationOperator]] = {}
        for bs_key, op_key in relations_to_set:
            bs_2_operators.setdefault(bs_key, []).append(
                operators_cache[op_key]
            )

        total = len(bs_2_operators)
        for index, (bs_key, operator_objs) in enumerate(
            bs_2_operators.items()
        ):
            PrettyPrint.progress_bar_info(
                index, total,
                'Обновление связей между BaseStation и BaseStationOperator:'
            )
            base_station = bs_cache[bs_key]

            current_operator_ids = set(
                base_station.operator.values_list('id', flat=True)
            )
            new_operator_ids = set(o.id for o in operator_objs)
            if current_operator_ids != new_operator_ids:
                base_station.operator.set(operator_objs)
