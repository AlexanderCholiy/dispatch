import uuid

from django.conf import settings


def generate_message_id(domain: str | None = None) -> str:
    domain = domain or settings.DEFAULT_DOMAIN
    return f'<{uuid.uuid4()}@{domain}>'
