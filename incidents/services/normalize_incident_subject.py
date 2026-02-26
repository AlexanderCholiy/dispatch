import re


def normalize_incident_subject(subject: str, incident_code: str | None) -> str:
    if not subject:
        return subject

    subject = subject.strip()

    # Убираем лишние Re/Fwd в начале
    pattern_re = r'^(?:\s*(?:Re|Fwd|FW)\s*:\s*)+'
    subject = re.sub(pattern_re, '', subject, flags=re.IGNORECASE)

    # Убираем существующий код в начале (если есть):
    if incident_code:
        pattern_code = rf'^\s*{re.escape(incident_code)}:\s*'
        subject = re.sub(pattern_code, '', subject, flags=re.IGNORECASE)

        subject = f'{incident_code}: {subject.strip()}'
    else:
        subject = subject.strip()

    return subject
