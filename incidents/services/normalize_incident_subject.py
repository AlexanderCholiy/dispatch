import re

from incidents.constants import INCIDENT_CODE_PREFIX
from yandex_tracker.utils import yt_manager


def normalize_incident_subject(subject: str, incident_code: str | None) -> str:
    """
    Нормализует тему письма:
    - оставляет один Re/Fwd/FW в начале, если было
    - удаляет старые коды инцидентов (NT-/AVRSERVICE-)
    - добавляет новый код инцидента
    - удаляет лишние Re/Fwd/FW в середине и конце темы
    """
    if not subject:
        subject = ''

    subject = subject.strip()

    # --- возможные префиксы кодов ---
    prefixes = [INCIDENT_CODE_PREFIX]
    if yt_manager and yt_manager.queue:
        prefixes.append(yt_manager.queue)
    prefixes_pattern = "|".join(map(re.escape, prefixes))

    # --- ищем Re/Fwd/FW в начале ---
    match = re.match(
        r'^(?:\s*(Re|Fwd|FW)\s*:\s*)+', subject, flags=re.IGNORECASE
    )
    prefix = ''
    if match:
        prefix = f'{match.group(1).capitalize()}: '
        subject = re.sub(
            r'^(?:\s*(Re|Fwd|FW)\s*:\s*)+', '', subject, flags=re.IGNORECASE
        ).strip()

    # --- удалить старые коды инцидентов ---
    subject = re.sub(
        rf'(?:^|\s)(?:{prefixes_pattern})-\d+\b:?\s*',
        ' ',
        subject,
        flags=re.IGNORECASE
    ).strip()

    # --- удалить все повторяющиеся Re/Fwd/FW в остальной строке ---
    subject = re.sub(
        r'\b(?:Re|Fwd|FW)\s*:\s*', '', subject, flags=re.IGNORECASE
    ).strip()

    # --- добавляем новый код инцидента ---
    if incident_code:
        subject = f'{incident_code}: {subject}' if subject else incident_code

    # --- возвращаем с Re: только если он был в начале ---
    return f'{prefix}{subject}'.strip()
