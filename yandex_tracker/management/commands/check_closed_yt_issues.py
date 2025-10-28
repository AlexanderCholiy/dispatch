import time
from functools import partial
from typing import Callable

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import OuterRef, Prefetch, Subquery
from django.utils import timezone

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.threads import tasks_in_threads
from core.wraps import min_wait_timer, timer
from incidents.constants import (
    AVR_CATEGORY,
    END_STATUS_NAME,
    GENERATION_STATUS_NAME,
)
from incidents.models import (
    Incident,
    IncidentCategory,
    IncidentCategoryRelation,
    IncidentStatus,
    IncidentStatusHistory,
)
from incidents.utils import IncidentManager
from yandex_tracker.constants import YT_ISSUES_DAYS_AGO_FILTER
from yandex_tracker.utils import YandexTrackerManager, yt_manager

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE
).get_logger()


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

    min_wait = 30

    def handle(self, *args, **kwargs):
        tg_manager.send_startup_notification(__name__)

        first_success_sent = False
        had_errors_last_time = False
        last_error_type = None

        while True:
            err = None
            total_errors = 0
            total_operations = 0
            total_updated = 0

            try:
                total_operations, total_errors, total_updated = (
                    self.check_closed_issues())
                if total_updated or total_errors:
                    yt_managment_logger.info(
                        f'Обработано {total_operations} закрытых '
                        f'инцидент(ов), обновлено {total_updated}, '
                        f'ошибок {total_errors}'
                    )
            except KeyboardInterrupt:
                return
            except Exception as e:
                yt_managment_logger.critical(e, exc_info=True)
                err = e
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
                if not first_success_sent and not total_errors:
                    tg_manager.send_first_success_notification(__name__)
                    first_success_sent = True

                if total_errors and not had_errors_last_time:
                    tg_manager.send_warning_counter_notification(
                        __name__, total_errors, total_operations
                    )

                had_errors_last_time = total_errors > 0

            finally:
                if err is not None and last_error_type != type(err).__name__:
                    tg_manager.send_error_notification(__name__, err)
                    last_error_type = type(err).__name__

    @min_wait_timer(yt_managment_logger, min_wait)
    @timer(yt_managment_logger)
    def check_closed_issues(self) -> tuple[int, int, int]:
        default_end_status, _ = IncidentStatus.objects.get_or_create(
            name=END_STATUS_NAME,
        )
        default_generation_status, _ = IncidentStatus.objects.get_or_create(
            name=GENERATION_STATUS_NAME,
        )

        total_processed = 0
        total_errors = 0
        total_updated = 0
        all_tasks: list[Callable] = []

        closed_issues_batches = yt_manager.closed_issues(
            YT_ISSUES_DAYS_AGO_FILTER)

        for i, closed_issues in enumerate(closed_issues_batches, 1):
            batch_total, batch_errors, batch_updated, tasks = (
                self.check_closed_batch_issues(
                    batch_number=i,
                    yt_manager=yt_manager,
                    closed_issues=closed_issues,
                    default_end_status=default_end_status,
                    default_generation_status=default_generation_status,
                )
            )
            total_processed += batch_total
            total_errors += batch_errors
            total_updated += batch_updated

            all_tasks.extend(tasks)

        tasks_in_threads(all_tasks, yt_managment_logger)

        return total_processed, total_errors, total_updated

    def check_closed_batch_issues(
        self,
        batch_number: int,
        yt_manager: YandexTrackerManager,
        closed_issues: list[dict],
        default_end_status: IncidentStatus,
        default_generation_status: IncidentStatus,
    ):
        """
        Работа с заявками в YandexTracker со статусом ЗАКРЫТО.

        Особенности:
            - Всем закрытым заявкам выставляем флаг закрытого инцидента, чтобы
            на диспетчеров могли равномерно распределяться заявки.
        """
        total = len(closed_issues)
        error_count = 0
        updated_count = 0

        validation_tasks = []

        incident_ids_to_update = set()
        database_ids_with_issues: list[tuple[int, dict]] = []

        for index, issue in enumerate(closed_issues):
            PrettyPrint.progress_bar_warning(
                index, total,
                f'Обработка закрытых заявок (стр.{batch_number}):'
            )

            database_id = issue.get(yt_manager.database_global_field_id)

            if database_id is not None:
                incident_ids_to_update.add(database_id)
                database_ids_with_issues.append((database_id, issue))
            else:
                yt_manager.create_incident_from_issue(issue, True)

        if not incident_ids_to_update:
            return total, error_count, updated_count

        # Подзапрос для последней даты статуса каждого инцидента:
        latest_status_id_subquery = (
            IncidentStatusHistory.objects
            .filter(incident=OuterRef('pk'))
            .order_by('-insert_date')
            .values('status_id')[:1]
        )

        incidents_queryset = (
            Incident.objects.filter(id__in=incident_ids_to_update)
            .select_related('incident_type')
            .prefetch_related(
                'categories',
                Prefetch(
                    'status_history',
                    queryset=(
                        IncidentStatusHistory.objects.select_related('status')
                        .order_by('-insert_date')
                    ),
                    to_attr='prefetched_statuses'
                ),
            )
            .annotate(last_status_id=Subquery(latest_status_id_subquery))
        )

        incidents_dict = {
            incident.pk: incident for incident in incidents_queryset
        }

        incidents_to_mark_finished = set()
        incidents_to_add_end_status: set[Incident] = set()
        incidents_to_add_generation_status: set[Incident] = set()
        incidents_2_update: list[Incident] = []

        default_inc_cat, _ = IncidentCategory.objects.get_or_create(
            name=AVR_CATEGORY
        )

        for database_id, issue in database_ids_with_issues:
            incident = incidents_dict.get(database_id)
            issue_key = issue['key']

            status_key: str = issue['status']['key']

            if not incident:
                yt_manager.create_incident_from_issue(issue, True)
                continue

            # Проверка и обновление кода:
            if incident.code != issue_key:
                incident.code = issue_key
                incidents_2_update.append(incident)

            # Проверка SLA:
            is_sla_avr_expired = issue.get(
                yt_manager.is_sla_avr_expired_global_field_id
            )
            is_sla_rvr_expired = issue.get(
                yt_manager.is_sla_rvr_expired_global_field_id
            )
            valid_is_sla_avr_expired = yt_manager.get_sla_avr_status(incident)
            valid_is_sla_rvr_expired = yt_manager.get_sla_rvr_status(incident)

            if (
                is_sla_avr_expired != valid_is_sla_avr_expired
                or is_sla_rvr_expired != valid_is_sla_rvr_expired
            ):
                validation_tasks.append(
                    partial(
                        yt_manager.update_issue_sla_status,
                        issue,
                        incident,
                    )
                )

            # Проверка признака завершённости:
            if not incident.is_incident_finish:
                incidents_to_mark_finished.add(database_id)

            # Проверка последнего статуса:
            last_status_id = incident.last_status_id

            if status_key == yt_manager.on_generation_status_key:
                if last_status_id != default_generation_status.pk:
                    incidents_to_add_generation_status.add(incident)
            else:
                if last_status_id != default_end_status.pk:
                    incidents_to_add_end_status.add(incident)

            # Проверка выставления даты начала SLA для АВР и РВР (АВР всегда
            # есть по умолчанию):
            categories = list(
                incident.categories.all().values_list('name', flat=True)
            )

            if not categories:
                IncidentCategoryRelation.objects.get_or_create(
                    incident=incident,
                    category=default_inc_cat
                )

            updated_avr_rvr_date = IncidentManager.auto_update_avr_rvr_dates(
                incident
            )

            if updated_avr_rvr_date:
                incidents_2_update.append(incident)

        if incidents_2_update:
            Incident.objects.bulk_update(
                incidents_2_update,
                [
                    'code',
                    'avr_start_date',
                    'avr_end_date',
                    'rvr_start_date',
                    'rvr_end_date',
                ]
            )

        if incidents_to_mark_finished:
            now = timezone.now()
            Incident.objects.filter(id__in=incidents_to_mark_finished).update(
                is_incident_finish=True,
                incident_finish_date=now,
            )
            updated_count += len(incidents_to_mark_finished)

        if incidents_to_add_end_status:
            with transaction.atomic():
                for incident in incidents_to_add_end_status:
                    incident.statuses.add(default_end_status)

        if incidents_to_add_generation_status:
            with transaction.atomic():
                for incident in incidents_to_add_generation_status:
                    incident.statuses.add(default_generation_status)

        return total, error_count, updated_count, validation_tasks
