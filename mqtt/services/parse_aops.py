import re
from datetime import datetime
from typing import Any, Optional

from core.loggers import mqtt_parser_logger
from mqtt.constants import ERR_PARSER_MSG_LIMIT, CellMeasurConstraints
from mqtt.shemas.aops import Cell, CellBar, CellMeasure, NetType, Operator


class ParseAops:

    def __init__(
        self,
        aops_raw: Optional[str],
        event_datetime: datetime,
        mongo_id: str,
    ):
        self.aops_raw = aops_raw
        self.event_datetime = event_datetime
        self.mongo_id = mongo_id

    def parse_aops_string(self) -> Optional[list[CellMeasure]]:
        if not self.aops_raw:
            return None

        found_anything = False

        strategies = [self._parse_aops_v1,]

        for strategy in strategies:
            result = None

            try:
                result = strategy()

                if result:
                    found_anything = True
                    break

            except KeyboardInterrupt:
                raise

            except Exception as e:
                mqtt_parser_logger.warning(
                    f'Ошибка при выполнении функции {strategy.__name__}: {e}'
                )
                continue

        if not found_anything and not self._is_service_message():
            mqtt_parser_logger.debug(
                'Не удалось распарсить данные ни одной стратегией '
                f'в {self.__class__.__name__}. '
                f'Сырые данные (первые {ERR_PARSER_MSG_LIMIT} символов):\n'
                f'{self.aops_raw[:ERR_PARSER_MSG_LIMIT]}'
            )
            return None

        return result

    def _parse_aops_v1(self) -> list[CellMeasure]:
        cells: list[CellMeasure] = []

        header_pattern = re.compile(
            r'^\+AOPS:"(?P<operator_name>[^"]*)",'
            r'"(?P<operator_st_name>[^"]*)",'
            r'"(?P<operator_code>[^"]*)"$'
        )

        measure_pattern = re.compile(
            r'^'
            r'(?P<index>\d+),'
            r'"(?P<rat>[^"]*)",'
            r'(?:Freq:(?P<freq>\d+),)?'
            r'(?P<signal_key>\w+):(?P<signal_val>-?\d+),'
            r'.*?'
            r'cellBar:(?P<cell_bar>\d+)'
            r'$'
        )

        kv_pattern = re.compile(r'(\w+):(-?\d+)')

        lines = self.aops_raw.splitlines()
        current_operator: Optional[Operator] = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            header_match = header_pattern.match(line)
            if header_match:
                data = header_match.groupdict()
                current_operator = Operator(
                    operator_code=data['operator_code'],
                    operator_name=data['operator_name'],
                    operator_st_name=data['operator_st_name']
                )
                continue

            if not current_operator:
                continue

            measure_match = measure_pattern.match(line)
            if measure_match:
                m_data = measure_match.groupdict()

                try:
                    index = m_data['index']
                    rat_str = m_data['rat']
                    freq = m_data['freq']
                    cell_bar_int = int(m_data['cell_bar'])
                    rat = NetType(rat_str)

                    all_kvs = dict(kv_pattern.findall(line))

                    cell_kwargs: dict[str, Any] = {}
                    measure_kwargs: dict[str, Any] = {}

                    cell_id = all_kvs['CellID']

                    cell_kwargs['cellid'] = cell_id
                    cell_kwargs['operator'] = current_operator
                    cell_kwargs['rat'] = rat
                    cell_kwargs['freq'] = freq

                    cell_kwargs['lac'] = all_kvs.get('LAC')
                    cell_kwargs['bsic'] = all_kvs.get('bsic')

                    rssi: Optional[str] = all_kvs.get('RSSI')
                    rssi = (
                        rssi
                        if rssi is not None
                        and int(rssi) >= CellMeasurConstraints.MIN_RSSI_VAL
                        and int(rssi) <= CellMeasurConstraints.MAX_RSSI_VAL
                        else None
                    )
                    measure_kwargs['rssi'] = rssi

                    rxlev: Optional[str] = all_kvs.get('rxLev')
                    rxlev = (
                        rxlev
                        if rxlev is not None
                        and int(rxlev) >= CellMeasurConstraints.MIN_RXLEV_VAL
                        and int(rxlev) <= CellMeasurConstraints.MAX_RXLEV_VAL
                        else None
                    )
                    measure_kwargs['rxlev'] = rxlev

                    c1: Optional[str] = all_kvs.get('c1')
                    c1 = (
                        c1
                        if c1 is not None
                        and int(c1) >= CellMeasurConstraints.MIN_C1_VAL
                        and int(c1) <= CellMeasurConstraints.MAX_C1_VAL
                        else None
                    )
                    measure_kwargs['c1'] = c1

                    cell_kwargs['lac'] = all_kvs.get('LAC')
                    cell_kwargs['psc'] = all_kvs.get('PSC')

                    rscp: Optional[str] = all_kvs.get('RSCP')
                    rscp = (
                        rscp
                        if rscp is not None
                        and int(rscp) >= CellMeasurConstraints.MIN_RSCP_VAL
                        and int(rscp) <= CellMeasurConstraints.MAX_RSCP_VAL
                        else None
                    )
                    measure_kwargs['rscp'] = rscp

                    # Контроллер вместо того чтобы отдать "Нет данных" отдает
                    # минимально возможное значение целочисленного типа.

                    ecno: Optional[str] = all_kvs.get('ecno')
                    ecno = (
                        ecno
                        if ecno is not None
                        and int(ecno) >= CellMeasurConstraints.MIN_ECNO_VAL
                        and int(ecno) <= CellMeasurConstraints.MAX_ECNO_VAL
                        else None
                    )
                    measure_kwargs['ecno'] = ecno

                    cell_kwargs['tac'] = all_kvs.get('TAC')
                    cell_kwargs['pci'] = all_kvs.get('PCI')

                    rsrp: Optional[str] = all_kvs.get('RSRP')
                    rsrp = (
                        rsrp
                        if rsrp is not None
                        and int(rsrp) >= CellMeasurConstraints.MIN_RSRP_VAL
                        and int(rsrp) <= CellMeasurConstraints.MAX_RSRP_VAL
                        else None
                    )
                    measure_kwargs['rsrp'] = rsrp

                    rsrq: Optional[str] = all_kvs.get('RSRQ')
                    rsrq = (
                        rsrq
                        if rsrq is not None
                        and int(rsrq) >= CellMeasurConstraints.MIN_RSRQ_VAL
                        and int(rsrq) <= CellMeasurConstraints.MAX_RSRQ_VAL
                        else None
                    )
                    measure_kwargs['rsrq'] = rsrq

                    measure_kwargs['cba'] = CellBar(cell_bar_int)

                    cell_obj = Cell(
                        event_datetime=self.event_datetime,
                        **cell_kwargs
                    )
                    measure_obj = CellMeasure(
                        cell=cell_obj,
                        index=index,
                        event_datetime=self.event_datetime,
                        mongo_id=self.mongo_id,
                        **measure_kwargs
                    )

                    cells.append(measure_obj)

                except (ValueError, KeyError) as e:
                    mqtt_parser_logger.warning(
                        f'Не удалось распарсить данные: {e}.\n'
                        'Сырые данные '
                        f'(первые {ERR_PARSER_MSG_LIMIT} символов):\n'
                        f'{self.aops_raw[:ERR_PARSER_MSG_LIMIT]}'
                    )
                    continue

        return cells

    def _is_service_message(self) -> bool:
        """Проверяет является ли ответ служебным выводом ошибки."""
        is_err_start = self.aops_raw.startswith('ERROR')

        if self.aops_raw == 'ERROR':
            return True

        if is_err_start and any(
            word in self.aops_raw for word in [
                'DISCONNECTED',
                'SMan"go',
                'Manufacturer:',
                'Model:',
                'Revision:',
                'KIL',
            ]
        ):
            return True

        if (
            is_err_start
            and '+EIntraINFO' in self.aops_raw
            and self.aops_raw.endswith('OK')
        ):
            pattern_aops = re.compile(
                r'^(?:NFO:|\+EIntraINFO:|\+CPOL:)',
                re.MULTILINE | re.IGNORECASE
            )
            if pattern_aops.search(self.aops_raw):
                return True

        lines = self.aops_raw.splitlines()
        last_line = lines[-1]

        if is_err_start:
            pattern_creg = re.compile(
                r'^\+CREG:\s*\d+,\s*[A-Fa-f0-9]+,\s*[A-Fa-f0-9]+$'
            )
            if pattern_creg.match(last_line):
                return True

        if is_err_start:
            pattern_creg = re.compile(
                r'^\+AOPS:\s*"[^"]*",\s*"[^"]*",\s*"\d+"$'
            )
            if pattern_creg.match(last_line):
                return True

        if is_err_start and last_line == 'K':
            pattern_aops = re.compile(
                r'\+AOPS:\s*"[^"]*",\s*"[^"]*",\s*"\d+"',
                re.IGNORECASE
            )
            if pattern_aops.search(self.aops_raw):
                return True

        return False
