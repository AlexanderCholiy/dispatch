import functools
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging import Logger
from typing import Callable, Optional


def get_task_name(task: Callable) -> str:
    """Возвращает короткое имя задачи для логирования."""
    if isinstance(task, functools.partial):
        func = task.func
        return getattr(func, '__name__', repr(func))

    if hasattr(task, '__name__'):
        return task.__name__

    return repr(task)


def tasks_in_threads(
    tasks: list[Callable],
    logger: Logger,
    cpu_bound: Optional[bool] = None
):
    """
    Выполняет список задач в потоках.
    Количество потоков подбирается динамически в зависимости от типа задач:
        cpu_bound=None - смешанные задачи, оптимально os.cpu_count() * 3
        cpu_bound=True - CPU-bound задачи, оптимально os.cpu_count()
        cpu_bound=False - I/O-bound задачи, оптимально os.cpu_count() * 10
    """
    if not tasks:
        logger.debug('Список задач пуст — выполнять нечего.')
        return

    if cpu_bound is None:
        threads_multiplier = 3  # смешанные
    elif cpu_bound is True:
        threads_multiplier = 1  # CPU-bound
    else:
        threads_multiplier = 10  # I/O-bound

    cpu_count = os.cpu_count() or 1
    max_workers = min(len(tasks), cpu_count * threads_multiplier)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_name = {}
        for task in tasks:
            task_name = get_task_name(task)
            logger.debug(f'Запуск задачи: {task_name}')
            future = executor.submit(task)
            future_to_name[future] = task_name

        for future in as_completed(future_to_name):
            task_name = future_to_name[future]
            try:
                future.result()
                logger.debug(f'Задача завершена успешно: {task_name}')
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.exception(
                    f'Ошибка при выполнении задачи {task_name}: {e}'
                )
