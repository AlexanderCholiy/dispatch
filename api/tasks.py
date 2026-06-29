from celery import Task, shared_task
from django.core.cache import cache
from django.db.models import Min
from django.utils import timezone

from api.services.update_energy_report import EnergyCSVBuilder
from api.services.update_incidents_report import IncidentsCsvBuilder
from core.loggers import celery_logger
from incidents.models import Incident

from .constants import (
    LOCK_ENERGY_BLOCKING_TIMEOUT_SEC,
    LOCK_ENERY_TIMEOUT_SEC,
    LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC,
    LOCK_INCIDENTS_TIMEOUT_SEC,
    LOCK_KEY_ACTUAL_INCIDENTS,
    LOCK_KEY_ARCHIVE_INCIDENTS,
    LOCK_KEY_CACHE_ENERGY_APPEALS_FILE,
    LOCK_KEY_CACHE_ENERGY_CLAIMS_FILE,
)


@shared_task(bind=True, ignore_result=True, queue='default')
def rebuild_actual_incidents(self):
    """Задача обновления CSV отчета (актуальные инциденты)."""
    lock_key = LOCK_KEY_ACTUAL_INCIDENTS

    with cache.lock(
        lock_key,
        timeout=LOCK_INCIDENTS_TIMEOUT_SEC,
        blocking_timeout=LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC
    ) as acquired:
        if not acquired:
            celery_logger.warning(
                'Задача обновления отчета по актуальным инцидентам '
                'уже запущена, пропуск.'
            )
            return

        builder = IncidentsCsvBuilder()
        builder.update_actual_file()


@shared_task(bind=True, ignore_result=True, queue='default')
def rebuild_archive_incidents(self, year: int, quarter: int):
    """Задача обновления архивного CSV отчета за конкретны год и квартал."""
    lock_key = f"{LOCK_KEY_ARCHIVE_INCIDENTS}_{year}_Q{quarter}"

    with cache.lock(
        lock_key,
        timeout=LOCK_INCIDENTS_TIMEOUT_SEC,
        blocking_timeout=LOCK_INCIDENTS_BLOCKING_TIMEOUT_SEC
    ) as acquired:
        if not acquired:
            celery_logger.warning(
                'Задача обновления отчета по архивным инцидентам '
                f'за {year}г. ({quarter} кв.) уже запущена, пропуск.'
            )
            return

        builder = IncidentsCsvBuilder()
        builder.update_archive_file(year, quarter)


@shared_task(bind=True, ignore_result=True, queue='default')
def rebuild_all_archives(self):
    """Задача обновления архивных CSV отчетов."""
    min_date_obj = (
        Incident.objects.aggregate(min_date=Min('incident_date'))['min_date']
    )

    if not min_date_obj:
        celery_logger.warning('Нет данных для архивации (бада пуста).')
        return

    min_date = min_date_obj.date()
    current_year = timezone.now().year
    start_year = min_date.year

    for year in range(start_year, current_year + 1):
        for q in range(1, 5):
            rebuild_archive_incidents.delay(year, q)


@shared_task(bind=True, ignore_result=True, queue='default')
def rebuild_energy_reports(self: Task):
    builder = EnergyCSVBuilder()

    # Блокировка для заявок (Claims)
    with cache.lock(
        LOCK_KEY_CACHE_ENERGY_CLAIMS_FILE,
        timeout=LOCK_ENERY_TIMEOUT_SEC,
        blocking_timeout=LOCK_ENERGY_BLOCKING_TIMEOUT_SEC
    ) as acquired:
        if not acquired:
            celery_logger.warning(
                'Обновление отчетов по заявкам энергетики уже запущено, '
                'пропуск.'
            )
        else:
            builder.update_claims_file()

    # Блокировка для обращений (Appeals)
    with cache.lock(
        LOCK_KEY_CACHE_ENERGY_APPEALS_FILE,
        timeout=LOCK_ENERY_TIMEOUT_SEC,
        blocking_timeout=LOCK_ENERGY_BLOCKING_TIMEOUT_SEC
    ) as acquired:
        if not acquired:
            celery_logger.warning(
                'Обновление отчетов по обращениям энергетики уже запущено, '
                'пропуск.'
            )
        else:
            builder.update_appeals_file()
