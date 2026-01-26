from celery import Task, shared_task
from django.core.cache import cache

from api.services.update_incidents_json import IncidentsJsonBuilder
from core.loggers import celery_logger

from .constants import (
    LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC,
    LOCK_INCIDENTS_TIMEOUT_SEC,
    LOCK_KEY_CACHE_INCIDENTS_FILE,
    LOCK_KEY_CACHE_INCIDENTS_LAST_MONTH_FILE,
)


@shared_task(bind=True, ignore_result=True, queue='default')
def rebuild_incidents_json(self: Task):
    builder = IncidentsJsonBuilder()

    with cache.lock(
        LOCK_KEY_CACHE_INCIDENTS_FILE,
        timeout=LOCK_INCIDENTS_TIMEOUT_SEC,
        blocking_timeout=LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC
    ) as acquired:
        if not acquired:
            celery_logger.warning(
                'Обновление отчетов по инцидентам уже запущено, пропуск.'
            )
            return

        builder.update_incident_file()

    with cache.lock(
        LOCK_KEY_CACHE_INCIDENTS_LAST_MONTH_FILE,
        timeout=LOCK_INCIDENTS_TIMEOUT_SEC,
        blocking_timeout=LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC
    ) as acquired:
        if not acquired:
            celery_logger.warning(
                'Обновление отчетов по инцидентам за месяц уже запущено, '
                'пропуск.'
            )
            return

        builder.update_incidents_last_month_file()
