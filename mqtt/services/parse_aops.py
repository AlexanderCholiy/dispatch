import re
from typing import Optional

from core.loggers import mqtt_logger
from mqtt.shemas.aops import AopsData, CellInfo, OperatorEntry


class ParseAops:

    def __init__(self, aops_raw: Optional[str]):
        self.aops_raw = aops_raw

    def parse_aops_string(self) -> Optional[AopsData]:
        if not self.aops_raw or self._is_service_message():
            return None

        result = AopsData()
        found_anything = False

        # Сначала более специфичные, потом общие:
        strategies = [
            self._parse_aops_v1,
            self._parse_aops_v2,
        ]

        for strategy in strategies:
            try:
                cells, ops = strategy()

                if cells:
                    result.cells.extend(cells)
                    found_anything = True
                if ops:
                    result.operators.extend(ops)
                    found_anything = True

            except KeyboardInterrupt:
                raise

            except Exception as e:
                mqtt_logger.warning(
                    f'Ошибка при выполнении функции {strategy.__name__}: {e}'
                )
                continue

        if not found_anything:
            mqtt_logger.error(
                f'Не удалось распарсить данные ни одной стратегией. '
                f'Сырые данные (первые 300 символов):\n{self.aops_raw[:300]}'
            )
            return None

        return result

    def _parse_aops_v1(self) -> tuple[list[CellInfo], list[OperatorEntry]]:
        cells = []
        ops = []

        pattern_cell = re.compile(
            r'''
            \+EIntraINFO: \s* (\d+),        # ID
            \s* MCC-MNC:  \s* ([^,\n]+?),   # MCC-MNC
            \s* TAC:      \s* (\d+),        # TAC
            \s* cellid:   \s* (\d+),        # CellID
            \s* rsrp:     \s* (-?\d+),      # RSRP
            \s* rsrq:     \s* (-?\d+),      # RSRQ
            \s* euArfcn:  \s* (\d+)         # euArfcn
            ''',
            re.VERBOSE | re.IGNORECASE
        )

        for match in pattern_cell.finditer(self.aops_raw):
            try:
                cells.append(CellInfo(
                    index=int(match.group(1)),
                    mcc_mnc=match.group(2).strip(),
                    tac=int(match.group(3)),
                    cellid=int(match.group(4)),
                    rsrp=int(match.group(5)),
                    rsrq=int(match.group(6)),
                    earfcn=int(match.group(7)),
                    net_type='4G'
                ))
            except ValueError as e:
                mqtt_logger.warning(
                    f'Ошибка валидации CellInfo: {e}. '
                    'Сырые данные (первые 300 символов):\n'
                    f'{self.aops_raw[:300]}'
                )
                continue

        pattern_op = re.compile(
            r'''
            \+CPOL:           # Поиск префикса команды AT+CPOL
            \s* (\d+),        # Группа 1: Индекс оператора в списке
            \s* (\d+),        # Группа 2: Статус (0-дл, 1-кр, 2-цифра)
            \s* ["\']?        # Опциональная открывающая кавычка
            ([^",\'\n]+)      # Группа 3: Оператор
            ["\']?            # Опциональная закрывающая кавычка
            ''',
            re.VERBOSE
        )
        for match in pattern_op.finditer(self.aops_raw):
            try:
                ops.append(OperatorEntry(
                    index=int(match.group(1)),
                    status=int(match.group(2)),
                    operator_code=match.group(3).strip()
                ))
            except ValueError as e:
                mqtt_logger.warning(
                    f'Ошибка валидации OperatorEntry: {e}. '
                    'Сырые данные (первые 300 символов):\n'
                    f'{self.aops_raw[:300]}'
                )
                continue

        return cells, ops

    def _parse_aops_v2(self) -> tuple[list[CellInfo], list[OperatorEntry]]:
        cells = []
        ops = []

        header_pattern = re.compile(
            r'''
            \+AOPS:\s*          # Префикс
            ["\']([^"\']+)["\'] # Группа 1: Имя оператора (первое поле)
            ,\s*
            ["\']([^"\']+)["\'] # Группа 2: Второе поле (часто дублирует имя)
            ,\s*
            ["\']([^"\']+)["\'] # Группа 3: Код оператора (третье поле)
            ''',
            re.VERBOSE | re.IGNORECASE
        )

        headers = list(header_pattern.finditer(self.aops_raw))

        if not headers:
            return [], []

        for i, header_match in enumerate(headers):
            op_name = header_match.group(1)
            op_code = header_match.group(3)

            ops.append(OperatorEntry(
                index=i + 1,
                status=None,
                operator_code=op_code,
                operator_name=op_name
            ))

            start_pos = header_match.end()
            end_pos = (
                headers[i + 1].start()
                if i + 1 < len(headers)
                else len(self.aops_raw)
            )
            block_text = self.aops_raw[start_pos:end_pos]

            # Строка вида: 1,"2G",Freq:70,RSSI:-72,bsic:14,LAC:27077...
            line_pattern = re.compile(
                r'''
                ^\s* (\d+) \s* ,      # Группа 1: Индекс
                \s* " ([^"]+) " \s* , # Группа 2: Тип сети
                \s* (.*)              # Группа 3: Параметры (до конца)
                ''',
                re.MULTILINE | re.VERBOSE
            )

            for line_match in line_pattern.finditer(block_text):
                idx = int(line_match.group(1))
                net_type = line_match.group(2).upper()
                params_str = line_match.group(3)

                param_map = {}
                for k, v in re.findall(r'(\w+):\s*(-?\d+)', params_str):
                    param_map[k.lower()] = int(v)

                # Конструируем объект CellInfo динамически
                cell_obj = CellInfo(index=idx, net_type=net_type)

                # Заполняем общие поля
                if 'cellid' in param_map:
                    cell_obj.cellid = param_map['cellid']
                if 'freq' in param_map:
                    cell_obj.freq = param_map['freq']

                # Специфичные поля по типу сети
                if net_type == '4G':
                    if 'rsrp' in param_map:
                        cell_obj.rsrp = param_map['rsrp']
                    if 'rsrq' in param_map:
                        cell_obj.rsrq = param_map['rsrq']
                    if 'pci' in param_map:
                        cell_obj.pci = param_map['pci']
                    if 'tac' in param_map:
                        cell_obj.tac = param_map['tac']
                    if 'earfcn' in param_map:
                        cell_obj.earfcn = param_map['earfcn']
                elif net_type == '3G':
                    if 'rscp' in param_map:
                        cell_obj.rscp = param_map['rscp']
                    if 'ecno' in param_map:
                        cell_obj.ecno = param_map['ecno']
                    if 'psc' in param_map:
                        cell_obj.psc = param_map['psc']
                    if 'lac' in param_map:
                        cell_obj.lac = param_map['lac']  # LAC для 3G
                elif net_type == '2G':
                    if 'rssi' in param_map:
                        cell_obj.rssi = param_map['rssi']
                    if 'bsic' in param_map:
                        cell_obj.bsic = param_map['bsic']
                    if 'lac' in param_map:
                        cell_obj.lac = param_map['lac']  # LAC для 2G
                    if 'rxlev' in param_map:
                        cell_obj.rxlev = param_map['rxlev']
                    if 'c1' in param_map:
                        cell_obj.c1 = param_map['c1']

                if any(
                    v is not None
                    for v in [cell_obj.rsrp, cell_obj.rscp, cell_obj.rssi]
                ):
                    cells.append(cell_obj)

        return cells, ops

    def _is_service_message(self) -> bool:
        """Проверяет, является ли текст служебным мусором (ошибка + статус)"""

        if not self.aops_raw:
            return True

        lines = [
            line.strip() for line in self.aops_raw.split('\n') if line.strip()
        ]
        if not lines:
            return True

        aops_keywords = ['+AOPS', '+EIntraINFO', '+CPOL']
        has_aops_data = any(
            any(kw in line for kw in aops_keywords) for line in lines
        )
        if has_aops_data:
            return False

        status_pattern = re.compile(
            r'^\+(C(R|G)?REG|COPS|CGATT|CSQ|CNSMOD)(.*)$'
            r'|^OK$|^ERROR$'
            r'|^[^+].*,.*$',
            re.IGNORECASE
        )
        first_line_is_error = lines[0] == 'ERROR'

        is_all_status = all(status_pattern.match(line) for line in lines)

        if first_line_is_error and is_all_status:
            return True

        if self.aops_raw.strip() == 'ERROR':
            return True

        return False
