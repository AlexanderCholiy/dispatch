import re
from typing import Any, Optional

from core.loggers import mqtt_logger
from mqtt.constants import ERR_PARSER_MSG_LIMIT
from mqtt.shemas.aops import Cell, CellBar, CellMeasure, NetType, Operator


class ParseAops:

    def __init__(self, aops_raw: Optional[str]):
        self.aops_raw = aops_raw

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
                mqtt_logger.warning(
                    f'Ошибка при выполнении функции {strategy.__name__}: {e}'
                )
                continue

        if not found_anything and not self._is_service_message():
            mqtt_logger.error(
                f'Не удалось распарсить данные ни одной стратегией. '
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

                    measure_kwargs['rssi'] = all_kvs.get('RSSI')
                    measure_kwargs['rxlev'] = all_kvs.get('rxLev')
                    measure_kwargs['c1'] = all_kvs.get('c1')

                    cell_kwargs['lac'] = all_kvs.get('LAC')
                    cell_kwargs['psc'] = all_kvs.get('PSC')

                    measure_kwargs['rscp'] = all_kvs.get('RSCP')
                    measure_kwargs['ecno'] = all_kvs.get('ecno')

                    cell_kwargs['tac'] = all_kvs.get('TAC')
                    cell_kwargs['pci'] = all_kvs.get('PCI')

                    measure_kwargs['rsrp'] = all_kvs.get('RSRP')
                    measure_kwargs['rsrq'] = all_kvs.get('RSRQ')

                    measure_kwargs['cba'] = CellBar(cell_bar_int)

                    cell_obj = Cell(**cell_kwargs)
                    measure_obj = CellMeasure(
                        cell=cell_obj,
                        index=index,
                        **measure_kwargs
                    )

                    cells.append(measure_obj)

                except (ValueError, KeyError) as e:
                    mqtt_logger.warning(
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

        if is_err_start and 'DISCONNECTED' in self.aops_raw:
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
