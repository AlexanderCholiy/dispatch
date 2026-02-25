import re


def normalize_incident_subject(subject: str, incident_code: str | None) -> str:
    if not subject:
        return subject

    subject = subject.strip()

    if not incident_code:
        return subject

    # Убираем существующий код в начале (если есть)
    pattern = rf'^\s*{re.escape(incident_code)}:\s*'
    subject = re.sub(pattern, '', subject, flags=re.IGNORECASE)

    return f'{incident_code}: {subject}'
