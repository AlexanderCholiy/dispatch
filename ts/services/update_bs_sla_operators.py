import numpy as np
import pandas as pd
from django.db import transaction
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import ts_logger
from ts.constants import BS_SLA_OPERATORS_FILE, DB_CHUNK_UPDATE
from ts.models import BaseStation, Pole


def update_bs_sla_operators():
    """
    Синхронизирует сроки устранения аварий (SLA) базовых станций из Excel.

    Скрипт выполняет быструю пакетную синхронизацию данных между файлом и базой
    данных PostgreSQL, минимизируя нагрузку на СУБД (использует bulk_update).

    Сценарии синхронизации (Логика работы):
        1. Изоляция дубликатов в файле:
           Если в Excel-файле присутствует несколько одинаковых связок
           [pole + bs_name], скрипт оставляет только последнюю строку
           (keep='last'), считая её актуальной.

        2. Обновление измененного SLA (Сценарий "Изменился"):
           Если связка [Опора + БС] найдена в базе данных, и её текущий SLA
           отличается от значения в файле (включая изменение числа на NULL/NaN
           или наоборот), значение перезаписывается новым из файла.

        3. Сброс отсутствующего SLA (Сценарий "Удален из файла / Обнуление"):
           Если БС существует в базе данных и у неё сейчас установлен
           какой-либо SLA, но этой БС (или её опоры) вообще нет в текущем
           Excel-файле — её SLA сбрасывается в `None` (NULL в БД).

        4. Игнорирование идентичных данных (Оптимизация трафика):
           Если данные в файле полностью совпадают с текущим состоянием БД,
           запись игнорируется и не участвует в транзакции на обновление.

        5. Пропуск записей без инфраструктуры (Сценарий "Нет опоры"):
           Если опора `pole` из файла отсутствует в таблице `Pole` в БД, запись
           пропускается (так как БС не может существовать без привязанной
           опоры).

    Исключения (Raises):
        ValueError: Если файл отсутствует по указанному пути.
        KeyError: Если в файле нет обязательных колонок
        ('pole', 'bs_name', 'sla_min').
    """

    if not BS_SLA_OPERATORS_FILE.exists():
        raise ValueError(
            f'Файл {BS_SLA_OPERATORS_FILE} со сроками устранения аварий '
            'по договорам отсутствует.'
        )

    filename = BS_SLA_OPERATORS_FILE.name

    df = pd.read_excel(BS_SLA_OPERATORS_FILE)

    required_columns = {'pole', 'bs_name', 'sla_min'}

    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        raise KeyError(f'В файле {filename} отсутствуют столбцы: {missing}')

    df = df.replace({np.nan: None})

    df['pole'] = df['pole'].astype('string').str.strip()
    df['bs_name'] = df['bs_name'].astype('string').str.strip()

    df = df.drop_duplicates(subset=['pole', 'bs_name'], keep='last')

    poles_map = {
        p['pole']: p['id']
        for p in (
            Pole.objects
            .filter(pole__in=df['pole'].unique()).values('id', 'pole')
        )
    }

    existing_stations = {
        (bs.pole_id, bs.bs_name): bs
        for bs in BaseStation.objects.only(
            'id', 'pole_id', 'bs_name', 'sla_contract_deadline'
        )
    }

    stations_to_update = []
    stations_to_reset = []

    # Множество для фиксации того, какие связки мы ОСТАВЛЯЕМ (они в файле):
    processed_in_file = set()

    with tqdm(
        total=len(df),
        desc=f'Обрабатываем записи, которые пришли в {filename}',
        colour='blue',
        position=0,
        leave=True,
        disable=not DEBUG_MODE,
    ) as pbar:
        for _, row in df.iterrows():
            pole_code = row['pole']
            bs_name = row['bs_name']
            sla_val = None
            if row['sla_min'] is not None:
                try:
                    sla_val = int(float(row['sla_min']))
                except (ValueError, TypeError):
                    sla_val = None
                    ts_logger.warning(
                        f'Некорректный SLA для {bs_name} ({pole_code}): '
                        f'{row["sla_min"]}'
                    )

            pole_id = poles_map.get(pole_code)
            if not pole_id:
                ts_logger.warning(
                    f'Неизвестная опора {pole_code} в файле {filename}.'
                )
                pbar.update(1)
                continue

            processed_in_file.add((pole_id, bs_name))

            station = existing_stations.get((pole_id, bs_name))
            if station and station.sla_contract_deadline != sla_val:
                station.sla_contract_deadline = sla_val
                stations_to_update.append(station)
            elif not station:
                ts_logger.warning(
                    f'БС {bs_name} (опора {pole_code}) '
                    f'найдена в файле {filename}, '
                    f'но отсутствует в БД.'
                )

            pbar.update(1)

    with tqdm(
        total=len(existing_stations),
        desc=f'Проверяем БС из базы, которых не было в файле {filename}',
        colour='red',
        position=0,
        leave=True,
        disable=not DEBUG_MODE,
    ) as pbar:
        for key, station in existing_stations.items():
            if (
                key not in processed_in_file
                and station.sla_contract_deadline is not None
            ):
                station.sla_contract_deadline = None
                stations_to_reset.append(station)

            pbar.update(1)

    if stations_to_update or stations_to_reset:
        with transaction.atomic():
            if stations_to_update:
                BaseStation.objects.bulk_update(
                    stations_to_update,
                    fields=['sla_contract_deadline'],
                    batch_size=DB_CHUNK_UPDATE,
                )

            if stations_to_reset:
                BaseStation.objects.bulk_update(
                    stations_to_reset,
                    fields=['sla_contract_deadline'],
                    batch_size=DB_CHUNK_UPDATE
                )

    ts_logger.debug(
        f'Успешно обновлено SLA записей БС из файла: {len(stations_to_update)}'
    )
    ts_logger.debug(
        f'Обнулен SLA у БС, отсутствующих в файле: {len(stations_to_reset)}'
    )
