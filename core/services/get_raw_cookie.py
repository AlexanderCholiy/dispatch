from typing import Optional
from urllib.parse import unquote

from django.http import HttpRequest

from core.loggers import django_logger


def get_raw_cookie(request: HttpRequest, name: str) -> Optional[str]:
    raw = request.COOKIES.get(name)
    if not raw:
        return None

    try:
        return unquote(raw)
    except Exception as e:
        django_logger.debug(f'Не удалось декодировать cookie: {name}: {e}')

    return None
