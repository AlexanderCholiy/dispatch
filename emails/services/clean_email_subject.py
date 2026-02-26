import re


def clean_email_subject(subject: str, incident_code: str | None) -> str:
    """Очищает тему письма от лишних Re:/Fwd:/старого кода."""
    if not subject:
        return subject

    subject = subject.strip()

    subject = re.sub(
        r'^(?:\s*(?:Re|Fwd|FW)\s*:\s*)+', '', subject, flags=re.IGNORECASE
    )

    if incident_code:
        pattern_code = rf'^\s*{re.escape(incident_code)}:\s*'
        subject = re.sub(pattern_code, '', subject, flags=re.IGNORECASE)
        subject = subject.strip()

    return subject
