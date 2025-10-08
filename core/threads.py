import os
from logging import Logger
from typing import Callable
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_task_name(task: Callable) -> str:
    """Возвращает короткое имя задачи для логирования."""
    if isinstance(task, functools.partial):
        func = task.func
        return getattr(func, '__name__', repr(func))

    if hasattr(task, '__name__'):
        return task.__name__

    return repr(task)


def tasks_in_threads(tasks: list[Callable], logger: Logger):
    """
    Выполняет список задач в потоках.
    Количество потоков подбирается динамически:
        - не более числа доступных CPU * 5 (IO-bound задачи)
        - не более числа задач
    """
    if not tasks:
        logger.debug('Список задач пуст — выполнять нечего.')
        return

    cpu_count = os.cpu_count() or 1
    max_workers = min(len(tasks), cpu_count * 5)

    logger.debug(
        f'Запуск {len(tasks)} задач в {max_workers} потоках'
    )

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
