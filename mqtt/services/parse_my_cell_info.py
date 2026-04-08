import re

from typing import Optional
from mqtt.shemas.aops import CellMeasure, Operator, Cell, NetType
from core.loggers import mqtt_logger
from mqtt.constants import ERR_PARSER_MSG_LIMIT


class ParseMyCellInfo:

    def __init__(self, my_cell_info_row: str):
        self.my_cell_info_row = my_cell_info_row

    def parse_my_cell_info_string(self) -> Optional[list[CellMeasure]]:
        if not self.my_cell_info_row:
            return None

        found_anything = False

        strategies = [self._parse_my_cell_info_v1]

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
                f'{self.my_cell_info_row[:ERR_PARSER_MSG_LIMIT]}'
            )
            return None

        return result

    def _parse_my_cell_info_v1(self) -> list[CellMeasure]:
        cells: list[CellMeasure] = []

        pattern = r'\+\s*MYCELLINFO:\s*\{\s*(\d+)\s*,\s*(.*?)\s*\}'
        match = re.search(pattern, self.my_cell_info_row, re.DOTALL)

        if not match:
            return cells

        cells_str = match.group(2)

        tuple_pattern = re.compile(
            r'\('
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*,'
            r'\s*(-?\d+)\s*'
            r'\)'
        )

        tuples = re.findall(tuple_pattern, cells_str)

        for t in tuples:
            try:
                # Распаковка согласно документации AT Commands Manual:
                idx = int(t[0])
                mcc = t[1]
                mnc = t[2]
                tac = int(t[3])
                cell_id = int(t[4])
                pci = int(t[5])
                rsrp_val = int(t[6])
                rsrq_val = int(t[7])
                rssi_val = int(t[8])

                op_code = f'{mcc}{mnc}'
                operator = Operator(operator_code=op_code)

                cell = Cell(
                    cellid=cell_id,
                    operator=operator,
                    rat=NetType.LTE,
                    lac=None,
                    tac=tac,
                    freq=None,
                    bsic=None,
                    psc=None,
                    pci=pci
                )

                measure = CellMeasure(
                    cell=cell,
                    index=idx,
                    rssi=rssi_val,
                    rxlev=None,
                    c1=None,
                    cba=None,
                    rscp=None,
                    ecno=None,
                    rsrp=rsrp_val,
                    rsrq=rsrq_val
                )

                cells.append(measure)

            except (ValueError, IndexError) as e:
                mqtt_logger.warning(
                    f'Не удалось распарсить данные: {e}.\n'
                    'Сырые данные '
                    f'(первые {ERR_PARSER_MSG_LIMIT} символов):\n'
                    f'{self.my_cell_info_row[:ERR_PARSER_MSG_LIMIT]}'
                )
                continue

        return cells

    def _is_service_message(self):
        return False
