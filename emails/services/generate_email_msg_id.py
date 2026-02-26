import uuid

from django.conf import settings


def generate_message_id() -> str:
    domain = settings.EMAIL_HOST
    return f'<{uuid.uuid4().hex}@{domain}>'
