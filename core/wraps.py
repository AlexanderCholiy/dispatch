import functools
import time
from datetime import datetime
from http import HTTPStatus
from logging import Logger
from typing import Callable

import requests

from .constants import API_STATUS_EXCEPTIONS
from .exceptions import ApiServerError, ApiTooManyRequests
from .utils import format_seconds


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
                    logger.debug(
                        f'Время выполнения {func.__name__}: {minutes} мин '
                        f'{round(seconds, 2)} сек'
                    )
                elif total_seconds >= 1:
                    seconds = round(total_seconds, 2)
                    logger.debug(
                        f'Время выполнения {func.__name__}: {seconds} сек'
                    )
                else:
                    milliseconds = round(execution_time.microseconds / 1000, 2)
                    logger.debug(
                        f'Время выполнения {func.__name__}: {milliseconds} мс'
                    )

        return wrapper
    return decorator


def retry(
    logger: Logger,
    retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Декоратор для повторного выполнения функции при ошибках.

    Args:
        logger (Logger): Логгер для записи ошибок.
        retries (int): Количество повторных попыток (по умолчанию 3)
        delay (float): Задержка между попытками в секундах (по умолчанию 1.0)
        exceptions: Кортеж исключений, при которых повторяем вызов
        передваваемой функции
        sub_func_name str: Имя подфункции для логирования.

    Особенности:
        Если передать в качестве kwarg sub_func_name, это имя будет
        использовано для логирования метода класса.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            sub_func_name = kwargs.pop('sub_func_name', None)
            msg_sub_func_name = (
                f'(метод {sub_func_name}) '
            ) if sub_func_name else ''

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
                        f'{msg_sub_func_name}'
                        f'с параметрами args={args} kwargs={kwargs} '
                        f'снова через {delay} секунд(ы)'
                    )
                    logger.debug(msg, exc_info=True)
                    time.sleep(delay)
        return wrapper
    return decorator


def safe_request(
    logger: Logger,
    retries: int = 3,
    timeout: int = 30,
) -> dict:
    """
    Декоратор для безопасного выполнения HTTP-запросов.

    Args:
        logger (Logger): Логгер для записи ошибок.
        retries (int): Количество повторных попыток (по умолчанию 3)
        timeout (int): Время выполнения на отправку запроса (по умолчанию 30)
        sub_func_name str: Имя подфункции для логирования.

    Returns:
        dict: Распарсенный JSON-ответ или {}.
    """

    def decorator(func):
        @retry(
            logger,
            retries=retries,
            delay=0,
            exceptions=(
                requests.exceptions.RequestException,
                ApiTooManyRequests,
                ApiServerError,
            ),
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            response: requests.Response = func(
                *args, timeout=timeout, **kwargs
            )

            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                retry_after = int(response.headers.get('Retry-After', timeout))
                time.sleep(retry_after)
                raise ApiTooManyRequests(
                    f'HTTP {response.status_code}: {response.text}'
                )

            if response.status_code in (
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.ACCEPTED,
                HTTPStatus.NO_CONTENT,
            ):
                try:
                    return response.json()
                except ValueError:
                    # logger.debug(f'Ответ {response.status_code}, но не JSON')
                    return {}

            if response.status_code == HTTPStatus.NO_CONTENT:
                return {}

            exc = API_STATUS_EXCEPTIONS.get(response.status_code)
            if exc:
                raise exc(
                    f'HTTP {response.status_code}: {response.text}'
                )

            if 500 <= response.status_code < 600:
                raise ApiServerError(
                    f'HTTP {response.status_code}: {response.text}'
                )

            raise requests.exceptions.RequestException(
                f'HTTP {response.status_code}: {response.text}'
            )

        return wrapper
    return decorator


def min_wait_timer(logger: Logger, min_seconds: int = 10):
    """
    Декоратор с минимальным временем выполнения функции.

    Args:
        min_seconds: Минимальное время выполнения в секундах.
            По умолчанию 10.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Callable:
            start_time = time.perf_counter()

            result = func(*args, **kwargs)

            execution_time = time.perf_counter() - start_time

            if execution_time < min_seconds:
                sleep_time = min_seconds - execution_time
                logger.debug(
                    f'Ждем {format_seconds(sleep_time)} секунд(ы) для '
                    f'завершения работы функции {func.__name__}'
                )
                time.sleep(sleep_time)

            return result
        return wrapper
    return decorator
