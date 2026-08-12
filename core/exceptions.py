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


class RateLimitExceeded(Exception):
    """
    Исключение, которое выбрасывается, если функция была вызвана слишком рано
    (меньше прошло времени TTL с последнего успешного запуска).
    """
    def __init__(self, func_name: str, remaining_seconds: int):
        self.func_name = func_name
        self.remaining_seconds = remaining_seconds
        message = (
            f'[Rate Limit] Запуск функции "{func_name}" отменен. '
            f'Слишком частый вызов. Осталось ждать: {remaining_seconds} сек.'
        )
        super().__init__(message)
