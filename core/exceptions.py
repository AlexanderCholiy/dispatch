class LoggerError(Exception):
    """Ошибка выбора режима работы логгера."""


class ApiUnauthorizedErr(Exception):
    """401 — Ошибка авторизации."""


class ApiForbidden(Exception):
    """403 — Доступ запрещён."""


class ApiNotFound(Exception):
    """404 — Ресурс не найден."""


class ApiMethodNotAllowed(Exception):
    """405 — Метод не разрешён для данного ресурса."""


class ApiTooManyRequests(Exception):
    """429 — Слишком много запросов."""


class ApiServerError(Exception):
    """5xx — Ошибки сервера."""


class ApiBadRequest(Exception):
    """400 — Некорректный запрос (ошибка тела или параметров)."""
