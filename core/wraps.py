import functools
import time
from datetime import datetime
from logging import Logger
from typing import Callable


def timer(logger: Logger) -> Callable:
    """Декоратор для измерения и логирования времени выполнения функции."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                return func(*args, **kwargs)
            finally:
                execution_time = datetime.now() - start_time
                total_seconds = execution_time.total_seconds()

                if total_seconds >= 60:
                    minutes = int(total_seconds // 60)
                    seconds = total_seconds % 60
                    logger.info(
                        f'Время выполнения {func.__name__}: {minutes} мин '
                        f'{round(seconds, 2)} сек'
                    )
                elif total_seconds >= 1:
                    seconds = round(total_seconds, 2)
                    logger.info(
                        f'Время выполнения {func.__name__}: {seconds} сек'
                    )
                else:
                    milliseconds = round(execution_time.microseconds / 1000, 2)
                    logger.info(
                        f'Время выполнения {func.__name__}: {milliseconds} мс'
                    )

        return wrapper
    return decorator


def retry(
    logger: Logger,
    retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Декоратор для повторного выполнения функции при ошибках.

    :param retries: Количество повторных попыток (по умолчанию 3)
    :param delay: Задержка между попытками в секундах (по умолчанию 1.0)
    :param exceptions: Кортеж исключений, при которых повторяем вызов
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt > retries:
                        raise
                    msg = (
                        f'Ошибка {e.__class__.__name__}. '
                        f'Попытка {attempt}/{retries}, '
                        f'пробуем запустить {func.__name__} '
                        f'с параметрами args={args} kwargs={kwargs} '
                        f'снова через {delay} секунд(ы)'
                    )
                    logger.warning(msg, exc_info=True)
                    time.sleep(delay)
        return wrapper
    return decorator


def safe_request(max_retries: int = 3, timeout: int = 10):
    """Декоратор для безопасного выполнения HTTP-запросов."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries <= max_retries:
                retries += 1
                try:
                    response: requests.Response = func(*args, timeout=timeout, **kwargs)

                    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                        retry_after = int(response.headers.get("Retry-After", 10))
                        time.sleep(retry_after)
                        continue

                    if response.status_code == HTTPStatus.OK:
                        return response.json()

                    if response.status_code == HTTPStatus.NO_CONTENT:
                        return {}

                    # другие ошибки
                    yt_manager_logger.critical(
                        f"Ошибка {response.status_code}: {response.text}"
                    )
                    raise YandexTrackerCriticalErr(response.status_code, response.text)

                except requests.exceptions.Timeout:
                    yt_manager_logger.warning(
                        f"Таймаут при запросе {func.__name__}"
                    )
                    raise YandexTrackerWarningErr(
                        HTTPStatus.REQUEST_TIMEOUT,
                        "Истекло время ожидания ответа от сервера."
                    )

                except requests.exceptions.RequestException as e:
                    yt_manager_logger.exception("Ошибка запроса")
                    raise YandexTrackerCriticalErr(
                        HTTPStatus.INTERNAL_SERVER_ERROR, str(e)
                    )

            # если все ретраи закончились
            raise YandexTrackerCriticalErr(
                HTTPStatus.TOO_MANY_REQUESTS,
                "Максимальное количество попыток исчерпано."
            )

        return wrapper
    return decorator
