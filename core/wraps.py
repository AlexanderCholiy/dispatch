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
