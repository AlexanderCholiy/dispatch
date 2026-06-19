import re

from incidents.models import Incident


def add_pole_2_subject(subject: str, pole: str | None) -> str:
    if not pole:
        return subject

    min_len = 5
    prefixes = [pole[:i] for i in range(min_len, len(pole) + 1)]

    escaped_prefixes = [re.escape(p) for p in prefixes]
    pattern_str = r'\b(' + '|'.join(escaped_prefixes) + r')\b'

    if re.search(pattern_str, subject, re.IGNORECASE):
        return subject

    return f'{subject} (опора {pole})'


def clean_email_subject(subject: str, incident: Incident) -> str:
    """Очищает тему письма от лишних Re:/Fwd:/старого кода."""
    incident_code: str | None = incident.code
    incident_pole: str | None = incident.pole.pole if incident.pole else None

    subject = subject.strip()

    subject = re.sub(
        r'^(?:\s*(?:Re|Fwd|FW)\s*:\s*)+', '', subject, flags=re.IGNORECASE
    )

    if incident_code:
        pattern_code = rf'^\s*{re.escape(incident_code)}:\s*'
        subject = re.sub(pattern_code, '', subject, flags=re.IGNORECASE)
        subject = subject.strip()

    return add_pole_2_subject(subject, incident_pole)
