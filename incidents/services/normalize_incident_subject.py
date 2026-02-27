import re


def normalize_incident_subject(subject: str, incident_code: str | None) -> str:
    """
    Нормализует тему письма:
    - убирает лишние повторы Re/Fwd, оставляя один;
    - аккуратно добавляет код инцидента в начале.
    """
    if not subject:
        return subject

    subject = subject.strip()

    # Убираем повторяющиеся Re/Fwd/FW (оставляем один, если есть)
    pattern_re = r'^(?:\s*(Re|Fwd|FW)\s*:\s*)+'
    match = re.match(pattern_re, subject, flags=re.IGNORECASE)
    if match:
        # оставляем только первый Re/Fwd
        first_tag = match.group(1).capitalize()
        subject = re.sub(pattern_re, '', subject, count=1, flags=re.IGNORECASE)
        subject = f'{first_tag}: {subject.strip()}'
    else:
        subject = subject.strip()

    # Добавляем код инцидента, если есть
    if incident_code:
        # проверим, не начинается ли уже с кода
        if not subject.lower().startswith(f'{incident_code.lower()}:'):
            subject = f'{incident_code}: {subject.strip()}'

    return subject
