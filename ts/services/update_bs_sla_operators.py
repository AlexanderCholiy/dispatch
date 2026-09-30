import numpy as np
import pandas as pd
from django.db import transaction
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import ts_logger
from ts.constants import BS_SLA_OPERATORS_FILE, DB_CHUNK_UPDATE
from ts.models import (
    BaseStation,
    BaseStationOperator,
    BaseStationOperatorContract,
    Pole,
)


class BSSLAOperatorsSync:
    """
    Синхронизация сроков устранения аварий (SLA) по договорам из Excel.

    Источник истины — файл. Таблица BaseStationOperatorContract
    перестраивается по нему целиком: совпадающие пары (БС, оператор)
    создаются или обновляются через ON CONFLICT, отсутствующие в файле
    договоры удаляются.

    Связь BaseStation.operator (M2M) этим скриптом НЕ изменяется.

    Обязательные колонки файла:
        'pole', 'bs_name', 'operator_name', 'operator_group', 'sla_min'

    Правила:
        1. Дубликаты [pole + bs_name + operator_name + operator_group]
           в файле схлопываются, остаётся последняя строка (keep='last').
        2. Если sla_min пуст/NULL или не парсится -> SLA = None.
        3. Если у БС нет данного оператора (нет связи в M2M) -> договор
           не создаётся, SLA не выставляется, строка логируется.
        4. Отсутствующие в БД опора / БС / оператор -> строка пропускается.
        5. Договоры, которых нет в файле -> удаляются.
        6. Совпадающие со значением в БД строки в UPDATE не попадают
           (их обрабатывает ON CONFLICT, изменения отсутствуют).

    Usage:
        BSSLAOperatorsSync().run()
    """

    REQUIRED_COLUMNS = frozenset({
        'pole',
        'bs_name',
        'operator_name',
        'operator_group',
        'sla_min',
    })

    TEXT_COLUMNS = ('pole', 'bs_name', 'operator_name', 'operator_group')

    DEDUPE_KEYS = [
        'pole',
        'bs_name',
        'operator_name',
        'operator_group',
    ]

    def __init__(self, file_path=BS_SLA_OPERATORS_FILE):
        self.file_path = file_path
        self.filename = file_path.name

        self.poles_map: dict[str, int] = {}
        self.stations_map: dict[tuple[int, str], int] = {}
        self.operators_map: dict[tuple[str, str | None], int] = {}
        self.m2m_links: set[tuple[int, int]] = set()

        self.skipped_unknown = 0
        self.skipped_no_link = 0
        self.invalid_sla = 0

    @transaction.atomic
    def run(self):
        """Полный цикл синхронизации. Возвращает статистику."""
        df = self._load_file()
        self._build_caches(df)
        rows = self._parse_rows(df)

        if not rows:
            ts_logger.warning(
                f'В файле {self.filename} нет применимых записей.'
            )
            stats = self._stats(0, 0)
            self._log_stats(stats)
            return

        upserted = self._upsert_contracts(rows)
        deleted = self._delete_stale(rows)

        stats = self._stats(upserted, deleted)
        self._log_stats(stats)

    def _load_file(self) -> pd.DataFrame:
        """Загрузка и подготовка файла"""
        if not self.file_path.exists():
            raise ValueError(
                f'Файл {self.file_path} со сроками устранения аварий '
                'по договорам отсутствует.'
            )

        df = pd.read_excel(self.file_path)

        if not self.REQUIRED_COLUMNS.issubset(df.columns):
            missing = self.REQUIRED_COLUMNS - set(df.columns)
            raise KeyError(
                f'В файле {self.filename} отсутствуют столбцы: {missing}'
            )

        df = df.replace({np.nan: None})

        for column in self.TEXT_COLUMNS:
            df[column] = df[column].astype('string').str.strip()

        for column in self.TEXT_COLUMNS:
            df[column] = (
                df[column]
                .astype('string')
                .str.strip()
                .replace({'': None})
            )

        df = df.drop_duplicates(subset=self.DEDUPE_KEYS, keep='last')

        return df

    def _build_caches(self, df: pd.DataFrame) -> None:
        """Кеши справочников"""
        self.poles_map = dict(
            Pole.objects.filter(pole__in=df['pole'].unique())
            .values_list('pole', 'id')
        )

        self.stations_map = {
            (pole_id, bs_name): bs_id
            for bs_id, pole_id, bs_name in BaseStation.objects.values_list(
                'id', 'pole_id', 'bs_name'
            )
        }

        self.operators_map = {
            (operator_name, operator_group): operator_id
            for operator_name, operator_group, operator_id in (
                BaseStationOperator.objects.filter(
                    operator_name__in=df['operator_name'].unique()
                ).values_list(
                    'operator_name', 'operator_group', 'id'
                )
            )
        }

        # M2M-привязки только по БС, упомянутым в файле
        candidate_bs_ids = {
            self.stations_map[(pole_id, bs_name)]
            for pole_id, bs_name in zip(
                (self.poles_map.get(p) for p in df['pole']),
                df['bs_name'],
            )
            if pole_id and (pole_id, bs_name) in self.stations_map
        }

        self.m2m_links = set(
            BaseStation.operator.through.objects.filter(
                basestation_id__in=candidate_bs_ids
            ).values_list('basestation_id', 'basestationoperator_id')
        ) if candidate_bs_ids else set()

    def _parse_rows(
        self, df: pd.DataFrame
    ) -> list[tuple[int, int, int | None]]:
        """Возвращает [(base_station_id, operator_id, sla), ...]."""
        rows = []

        for _, row in tqdm(
            df.iterrows(),
            total=len(df),
            desc=f'Обрабатываем записи из {self.filename}',
            colour='blue',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ):
            ids = self._resolve_ids(row)
            if ids is None:
                continue

            base_station_id, operator_id = ids

            # у БС нет такого оператора -> SLA не выставляем
            if (base_station_id, operator_id) not in self.m2m_links:
                self.skipped_no_link += 1
                ts_logger.debug(
                    f'Оператор {row["operator_name"]} '
                    f'(группа {row["operator_group"]}) не привязан к БС '
                    f'{row["bs_name"]} (опора {row["pole"]}) — SLA пропущен.'
                )
                continue

            rows.append(
                (base_station_id, operator_id, self._parse_sla(row))
            )

        return rows

    def _resolve_ids(self, row) -> tuple[int, int] | None:
        pole_id = self.poles_map.get(row['pole'])
        if not pole_id:
            self.skipped_unknown += 1
            ts_logger.debug(
                f'Неизвестная опора {row["pole"]} в файле {self.filename}.'
            )
            return None

        base_station_id = self.stations_map.get((pole_id, row['bs_name']))
        if not base_station_id:
            self.skipped_unknown += 1
            ts_logger.debug(
                f'БС {row["bs_name"]} (опора {row["pole"]}) найдена в файле '
                f'{self.filename}, но отсутствует в БД.'
            )
            return None

        operator_id = self.operators_map.get(
            (row['operator_name'], row['operator_group'])
        )
        if not operator_id:
            self.skipped_unknown += 1
            ts_logger.debug(
                f'Оператор {row["operator_name"]} '
                f'(группа {row["operator_group"]}) из файла '
                f'{self.filename} отсутствует в БД.'
            )
            return None

        return base_station_id, operator_id

    def _parse_sla(self, row) -> int | None:
        raw_value = row['sla_min']

        if raw_value is None:
            return None

        try:
            return int(float(raw_value))
        except (ValueError, TypeError):
            self.invalid_sla += 1
            ts_logger.warning(
                f'Некорректный SLA для {row["bs_name"]} '
                f'({row["pole"]}) / {row["operator_name"]}: '
                f'{raw_value!r}'
            )
            return None

    def _upsert_contracts(
        self, rows: list[tuple[int, int, int | None]]
    ) -> int:
        """Запись в БД"""
        contracts = [
            BaseStationOperatorContract(
                base_station_id=base_station_id,
                operator_id=operator_id,
                sla_contract_deadline=sla,
            )
            for base_station_id, operator_id, sla in rows
        ]

        BaseStationOperatorContract.objects.bulk_create(
            contracts,
            update_conflicts=True,
            unique_fields=['base_station', 'operator'],
            update_fields=['sla_contract_deadline'],
            batch_size=DB_CHUNK_UPDATE,
        )

        return len(contracts)

    def _delete_stale(
        self, rows: list[tuple[int, int, int | None]]
    ) -> int:
        """Удаление неактуального"""
        keep = {
            (base_station_id, operator_id)
            for base_station_id, operator_id, _ in rows
        }

        stale_pks = [
            contract_id
            for base_station_id, operator_id, contract_id in (
                BaseStationOperatorContract.objects.values_list(
                    'base_station_id', 'operator_id', 'id'
                )
            )
            if (base_station_id, operator_id) not in keep
        ]

        deleted = 0
        for chunk in self._chunked(stale_pks, DB_CHUNK_UPDATE):
            count, _ = BaseStationOperatorContract.objects.filter(
                id__in=chunk
            ).delete()
            deleted += count

        return deleted

    @staticmethod
    def _chunked(items, size):
        items = list(items)
        for i in range(0, len(items), size):
            yield items[i:i + size]

    def _stats(self, upserted: int, deleted: int) -> dict[str, int]:
        return {
            'upserted': upserted,
            'deleted': deleted,
            'skipped_unknown': self.skipped_unknown,
            'skipped_no_link': self.skipped_no_link,
            'invalid_sla': self.invalid_sla,
        }

    def _log_stats(self, stats: dict[str, int]) -> None:
        ts_logger.debug(
            f'SLA по договорам из {self.filename}: '
            f'создано/обновлено {stats["upserted"]}, '
            f'удалено неактуальных {stats["deleted"]}.'
        )

        if stats['skipped_unknown']:
            ts_logger.warning(
                'Пропущено строк из-за отсутствующих опор/БС/операторов: '
                f'{stats["skipped_unknown"]}'
            )

        if stats['skipped_no_link']:
            ts_logger.warning(
                f'Пропущено строк без привязки оператора к БС: '
                f'{stats["skipped_no_link"]}'
            )

        if stats['invalid_sla']:
            ts_logger.warning(
                f'Строк с некорректным значением sla_min: '
                f'{stats["invalid_sla"]}'
            )
