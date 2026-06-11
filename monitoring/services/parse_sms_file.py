import re

from typing import TypedDict, Optional
from datetime import datetime

from pathlib import Path
from monitoring.shemas.rvr_sms import SMSParseSchema
from core.loggers import monitoring_rvr_sms_logger


class SMSResponse(TypedDict):
    phone_from: Optional[str]
    phone_to: Optional[str]
    sent_time: Optional[datetime]
    received_time: Optional[datetime]
    answer: Optional[str]


def parse_sms_file(file_path: Path) -> SMSParseSchema:
    content = file_path.read_text(encoding='utf-8')

    # Регулярные выражения для поиска значений
    # \s+ - один или более пробелов после двоеточия:
    pattern_from = r'^From:\s*(\d+)$'
    pattern_smsc = r'^From_SMSC:\s*(\d+)$'
    pattern_sent = r'^Sent:\s*(.+)$'
    pattern_recv = r'^Received:\s*(.+)$'

    date_format = '%y-%m-%d %H:%M:%S'

    data: SMSParseSchema = {}
    lines = content.splitlines()
    answer_candidate = None

    ignore_keys = [
        'From:', 'From_TOA:', 'From_SMSC:', 'Sent:', 'Received:',
        'Subject:', 'Modem:', 'IMSI:', 'IMEI:', 'Report:',
        'Alphabet:', 'Length:'
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Парсим основные поля:
        if match := re.match(pattern_from, line):
            data['phone_from'] = match.group(1)
        elif match := re.match(pattern_smsc, line):
            data['phone_to'] = match.group(1)
        elif match := re.match(pattern_sent, line):
            sent_time = match.group(1)
            try:
                data['sent_time'] = datetime.strptime(
                    sent_time, date_format
                )
            except ValueError as e:
                monitoring_rvr_sms_logger.warning(
                    f'{file_path.name}: Ошибка формата даты/времени: {e}'
                )
        elif match := re.match(pattern_recv, line):
            received_time = match.group(1)
            try:
                data['received_time'] = datetime.strptime(
                    received_time, date_format
                )
            except ValueError as e:
                monitoring_rvr_sms_logger.warning(
                    f'{file_path.name}: Ошибка формата даты/времени: {e}'
                )
        else:
            if (
                not any(line.startswith(k) for k in ignore_keys)
                and len(line) > 1
            ):
                answer_candidate = line

                if not all(c.isdigit() or c.isspace() for c in line):
                    monitoring_rvr_sms_logger.debug(
                        f'{file_path.name}: '
                        f'Подозрительный ответ: {answer_candidate}'
                    )

    if answer_candidate:
        data['answer'] = answer_candidate

    return SMSParseSchema.model_validate(data)
