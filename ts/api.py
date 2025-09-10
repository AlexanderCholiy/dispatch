import json
import os
from http import HTTPStatus
from types import NoneType

import pandas as pd
import requests
from django.db import IntegrityError, transaction
from numpy import nan

from core.constants import TS_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.wraps import timer

from .constants import (
    AVR_FILE,
    BASE_STATIONS_FILE,
    COLUMNS_TO_KEEP_AVR_REPORT,
    COLUMNS_TO_KEEP_BS_OPERATORS_REPORT,
    COLUMNS_TO_KEEP_POLES_TL,
    POLES_FILE,
    TS_AVR_REPORT_URL,
    TS_BS_REPORT_URL,
    TS_POLES_TL_URL,
    UNDEFINED_CASE,
    UNDEFINED_EMAILS,
)
from .models import (
    AVRContractor,
    BaseStation,
    BaseStationOperator,
    ContractorEmail,
    ContractorPhone,
    Pole,
)
from .validators import SocialValidators

ts_api_logger = LoggerFactory(__name__, TS_LOG_ROTATING_FILE).get_logger


class Api(SocialValidators):
    """Загрузка данных из TS и добавление их в БД"""

    @staticmethod
    @timer(ts_api_logger)
    def download_json(json_file_path: str, url: str, chunk_size: int = 1000):
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

    @staticmethod
    def json_2_df(
        json_file_path: str, columns_to_keep: list[str]
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

    @staticmethod
    def update_poles(update_json: bool = True):
        if update_json or not os.path.exists(POLES_FILE):
            Api.download_json(POLES_FILE, TS_POLES_TL_URL)

        poles = Api.json_2_df(POLES_FILE, COLUMNS_TO_KEEP_POLES_TL)
        poles['SiteId'] = poles['SiteId'].astype(int)
        poles['Широта'] = poles['Широта'].astype(float)
        poles['Долгота'] = poles['Долгота'].astype(float)
        poles['Высота опоры'] = poles['Высота опоры'].astype(float)
        total = len(poles)

        # Удаляем не актуальные записи:
        new_site_ids: set[int] = set(poles['SiteId'])
        existing_site_ids: set[int] = set(
            Pole.objects.values_list('site_id', flat=True))
        site_ids_to_delete = (
            existing_site_ids
            - new_site_ids
            - {UNDEFINED_CASE}
        )
        if site_ids_to_delete:
            Pole.objects.filter(site_id__in=site_ids_to_delete).delete()

        # Добавляем опору по умолчанию:
        Pole.add_default_value()

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
            region = row['Регион'] or None
            address = row['Адрес'] or None
            infrastructure_company = row['Инфраструктурная компания'] or None
            anchor_operator = row['Якорный оператор'] or None

            if (
                not isinstance(site_id, int)
                or not isinstance(pole, str)
                or not isinstance(bs_name, str)
                or not isinstance(pole_status, (str, NoneType))
                or not isinstance(pole_latitude, (float, NoneType))
                or not isinstance(pole_longtitude, (float, NoneType))
                or not isinstance(pole_height, (float, NoneType))
                or not isinstance(region, (str, NoneType))
                or not isinstance(address, (str, NoneType))
                or not isinstance(infrastructure_company, (str, NoneType))
                or not isinstance(anchor_operator, (str, NoneType))
            ):
                find_unvalid_values = True
                continue

            try:
                Pole.objects.update_or_create(
                    site_id=site_id,
                    defaults={
                        'pole': pole,
                        'bs_name': bs_name,
                        'pole_status': pole_status,
                        'pole_latitude': pole_latitude,
                        'pole_longtitude': pole_longtitude,
                        'pole_height': pole_height,
                        'region': region,
                        'address': address,
                        'infrastructure_company': infrastructure_company,
                        'anchor_operator': anchor_operator,
                    },
                )
            except IntegrityError:
                find_unvalid_values = True

        if find_unvalid_values:
            ts_api_logger.warning(f'Проверьте данные в {TS_POLES_TL_URL}')

    @staticmethod
    def update_avr(update_json: bool = True):
        if update_json or not os.path.exists(AVR_FILE):
            Api.download_json(AVR_FILE, TS_AVR_REPORT_URL)

        avr = Api.json_2_df(AVR_FILE, COLUMNS_TO_KEEP_AVR_REPORT)
        total = len(avr)

        # Удаляем не актуальные записи:
        new_project_ids: set[int] = set(avr['Подрядчик'])
        existing_project_ids: set[int] = set(
            AVRContractor.objects.values_list('contractor_name', flat=True))
        project_ids_to_delete = (
            existing_project_ids
            - new_project_ids
            - {UNDEFINED_CASE}
        )
        if project_ids_to_delete:
            AVRContractor.objects.filter(
                project_id__in=project_ids_to_delete).delete()

        # Добавляем подрядчика по умолчанию:
        with transaction.atomic():
            default_contractor, is_up = AVRContractor.objects.update_or_create(
                contractor_name=UNDEFINED_CASE,
                defaults={'is_excluded_from_contract': False}
            )

            email_objs = []
            for email in UNDEFINED_EMAILS:
                email_obj, _ = ContractorEmail.objects.get_or_create(
                    email=email)
                email_objs.append(email_obj)
            if is_up:
                default_contractor.emails.set(email_objs)

            pole = Pole.add_default_value()
            pole.avr_contractor = default_contractor
            pole.save()

        # Обновляем актуальные записи:
        find_unvalid_values = False
        poles_cache = {p.pole: p for p in Pole.objects.all()}

        for index, row in avr.iterrows():
            PrettyPrint.progress_bar_info(
                index, total,
                (
                    'Обновление AVRContractor, ContractorEmail, '
                    'ContractorPhone и связи между AVRContractor и Poles:'
                )
            )

            is_excluded_from_contract = (
                row['Исключен из договора'].strip().lower() != 'нет'
            )
            pole_number = row['Шифр опоры']
            contractor_name = row['Подрядчик'] or None
            contractor_emails = row['Контактные данные подрядчика Email']
            contractor_phones = row['Контактные данные подрядчика Телефон']

            if (
                not isinstance(is_excluded_from_contract, bool)
                or not isinstance(pole_number, str)
                or not isinstance(contractor_name, (str, NoneType))
                or not isinstance(contractor_emails, (str, NoneType))
                or not isinstance(contractor_phones, (str, NoneType))
            ):
                find_unvalid_values = True
                continue

            if contractor_emails:
                valid_contractor_emails, _ = Api.split_and_validate_emails(
                    contractor_emails)
            else:
                # Чтобы заявки на АВР приходили на emails по умолчанию:
                valid_contractor_emails = UNDEFINED_EMAILS

            if contractor_phones:
                valid_contractor_phones, _ = Api.split_and_validate_phones(
                    contractor_phones)
            else:
                valid_contractor_phones = []

            if contractor_name:
                try:
                    with transaction.atomic():
                        contractor, _ = AVRContractor.objects.update_or_create(
                            contractor_name=contractor_name,
                            defaults={
                                'is_excluded_from_contract': (
                                    is_excluded_from_contract)
                            }
                        )

                        email_objs = []
                        for email in valid_contractor_emails:
                            email_obj, _ = (
                                ContractorEmail
                                .objects.get_or_create(email=email)
                            )
                            email_objs.append(email_obj)
                        contractor.emails.set(email_objs)

                        phone_objs = []
                        for phone in valid_contractor_phones:
                            phone_obj, _ = (
                                ContractorPhone
                                .objects.get_or_create(phone=phone)
                            )
                            phone_objs.append(phone_obj)
                        contractor.phones.set(phone_objs)

                        pole = poles_cache.get(pole_number)
                        if pole:
                            pole.avr_contractor = contractor
                            pole.save()

                except IntegrityError:
                    find_unvalid_values = True

            else:
                pole = poles_cache.get(pole_number)
                if pole:
                    pole.avr_contractor = default_contractor
                    pole.save()

        if find_unvalid_values:
            ts_api_logger.warning(f'Проверьте данные в {TS_AVR_REPORT_URL}')

    @staticmethod
    def update_base_stations(update_json: bool = True):
        if update_json or not os.path.exists(BASE_STATIONS_FILE):
            Api.download_json(BASE_STATIONS_FILE, TS_BS_REPORT_URL)

        base_stations = Api.json_2_df(
            BASE_STATIONS_FILE, COLUMNS_TO_KEEP_BS_OPERATORS_REPORT)
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
            existing_bs_combinations - new_bs_combinations)
        if combinations_bs_to_delete:
            BaseStation.objects.filter(
                pole__pole__in=[comb[0] for comb in combinations_bs_to_delete],
                bs_name__in=[comb[1] for comb in combinations_bs_to_delete]
            ).delete()

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
            existing_operators_combinations - new_operators_combinations)
        if combinations_operators_to_delete:
            BaseStationOperator.objects.filter(
                operator_name__in=[
                    comb[0] for comb in combinations_operators_to_delete
                ],
                operator_group__in=[
                    comb[1] for comb in combinations_operators_to_delete
                ]
            ).delete()

        # Обновляем актуальные записи:
        # Кешируем все существующие опоры и операторы для быстрого доступа:
        poles = {p.pole: p for p in Pole.objects.all()}
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

            with transaction.atomic():
                base_station, _ = BaseStation.objects.get_or_create(
                    bs_name=bs_name,
                    pole=pole,
                )

                bs_filter = (
                    (base_stations['Шифр опоры'] == pole_number)
                    & (base_stations['Имя БС/Оборудование'] == bs_name)
                )
                filtered_base_stations = base_stations[bs_filter]
                operators_data = list(set(zip(
                    filtered_base_stations['Оператор'],
                    filtered_base_stations['Группа операторов']
                )))

                valid_operators = []
                for operator_name, operator_group in operators_data:
                    operator_obj, _ = (
                        BaseStationOperator.objects.get_or_create(
                            operator_name=operator_name,
                            operator_group=operator_group,
                        )
                    )
                    valid_operators.append(operator_obj)

                base_station.operator.set(valid_operators)

        if find_unvalid_values:
            ts_api_logger.warning(f'Проверьте данные в {TS_BS_REPORT_URL}')
