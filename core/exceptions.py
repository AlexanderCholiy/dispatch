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


class ConfigEnvError(Exception):
    """Исключение для отсутствующих переменных конфигурации."""

    def __init__(self, missing_vars: list[str]):
        self.missing_vars = missing_vars
        missing_vars_str = ', '.join(missing_vars)
        super().__init__(
            'Ошибка конфигурации. Отсутствуют переменные '
            f'{missing_vars_str} в .env файле.'
        )
