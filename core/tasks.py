import time
from datetime import timedelta

from celery import Task, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone
from django_celery_results.models import GroupResult, TaskResult

from .loggers import celery_logger


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    soft_time_limit=10,
    time_limit=15,
    queue='low'
)
def fail_test_task(self: Task, n: int) -> int:
    """Задача с ошибкой и повторной попыткой"""
    try:
        if n % 2 == 0:
            raise ValueError('Inner error')
        return n * 2
    except Exception as exc:
        celery_logger.warning(
            f'Повтор {fail_test_task.__name__} причина:\n{exc}'
        )
        raise self.retry(exc=str(exc))


@shared_task(bind=True, soft_time_limit=3, time_limit=5, queue='medium')
def limit_test_task(self: Task) -> None:
    try:
        time.sleep(10)
    except SoftTimeLimitExceeded:
        celery_logger.error('Превышение SoftTimeLimitExceeded')
        raise


@shared_task(bind=True, queue='high')
def group_test_task(self: Task, x: int) -> int:
    """Групповая задача"""
    return x**2


@shared_task(bind=True, queue='heavy')
def heavy_test_task(self: Task) -> None:
    """Тяжёлая задача для теста нагрузки"""


@shared_task(bind=True, queue='default')
def cleanup_old_task_results(self: Task) -> None:
    """Удаляет старые записи TaskResult согласно CELERY_RESULT_EXPIRES"""
    expires_seconds = settings.CELERY_RESULT_EXPIRES
    threshold = timezone.now() - timedelta(seconds=expires_seconds)

    deleted_tasks, _ = (
        TaskResult.objects.filter(date_done__lt=threshold).delete()
    )
    celery_logger.info(f'Удалено {deleted_tasks} старых записей TaskResult')

    deleted_groups, _ = (
        GroupResult.objects.filter(date_done__lt=threshold).delete()
    )
    celery_logger.info(f'Удалено {deleted_groups} старых записей GroupResult')
