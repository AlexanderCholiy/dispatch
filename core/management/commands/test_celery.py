
from celery import group
from celery.result import AsyncResult, GroupResult
from django.core.management.base import BaseCommand

from core import tasks
from core.loggers import celery_logger


class Command(BaseCommand):
    help = 'Тестирование Celery и RabbitMQ'

    def handle(self, *args, **options):
        # Задача с ошибкой
        fail_test_task: AsyncResult = tasks.fail_test_task.delay(2)
        celery_logger.debug(
            f'{tasks.fail_test_task.__name__} ID: {fail_test_task.id}'
        )

        # Soft time limit
        limit_test_task: AsyncResult = tasks.limit_test_task.delay()
        celery_logger.debug(
            f'{tasks.limit_test_task.__name__} ID: {limit_test_task.id}'
        )

        # Групповая задача
        job: GroupResult = group(
            [tasks.group_test_task.s(i) for i in range(5)]
        )()
        job.save()
        celery_logger.debug(
            f'{tasks.group_test_task.__name__} ID: {job.id}'
        )
