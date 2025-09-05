import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import OuterRef, Subquery

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.wraps import min_wait_timer, timer
from incidents.constants import (
    DEFAULT_END_STATUS_DESC,
    DEFAULT_END_STATUS_NAME,
)
from incidents.models import Incident, IncidentStatus, IncidentStatusHistory
from yandex_tracker.constants import YT_ISSUES_DAYS_AGO_FILTER
from yandex_tracker.utils import YandexTrackerManager, yt_manager

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


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
            error_count = 0
            total_operations = 0

            try:
                self.check_closed_issues(yt_manager)
            except KeyboardInterrupt:
                return
            except Exception as e:
                yt_managment_logger.critical(e, exc_info=True)
                err = e
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
                if not first_success_sent and not error_count:
                    tg_manager.send_first_success_notification(__name__)
                    first_success_sent = True

                if error_count and not had_errors_last_time:
                    tg_manager.send_warning_counter_notification(
                        __name__, error_count, total_operations
                    )

                had_errors_last_time = error_count > 0

            finally:
                if err is not None and last_error_type != type(err).__name__:
                    tg_manager.send_error_notification(__name__, err)
                    last_error_type = type(err).__name__

    @min_wait_timer(yt_managment_logger, min_wait)
    @timer(yt_managment_logger)
    def check_closed_issues(self, yt_manager: YandexTrackerManager):
        """
        Работа с заявками в YandexTracker со статусом ЗАКРЫТО.

        Особенности:
            - Всем закрытым заявкам выставляем флаг закрытого инцидента, чтобы
            на диспетчеров могли равномерно распределяться заявки.
        """

        closed_issues = yt_manager.closed_issues(YT_ISSUES_DAYS_AGO_FILTER)
        total = len(closed_issues)

        if total == 0:
            return

        incident_ids_to_update = set()
        database_ids_with_issues = []

        for index, issue in enumerate(closed_issues):
            PrettyPrint.progress_bar_warning(
                index, total, 'Обработка закрытых заявок:')

            database_id = issue.get(yt_manager.database_global_field_id)
            if database_id is not None:
                incident_ids_to_update.add(database_id)
                database_ids_with_issues.append((database_id, issue))
            else:
                is_sla_expired = issue.get(
                    yt_manager.is_sla_expired_global_field_id)

        if not incident_ids_to_update:
            return

        default_end_status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_END_STATUS_NAME,
            defaults={'description': DEFAULT_END_STATUS_DESC}
        )

        # Подзапрос для последней даты статуса каждого инцидента:
        latest_status_subquery = IncidentStatusHistory.objects.filter(
            incident=OuterRef('pk')
        ).order_by('-insert_date').values('insert_date')[:1]

        incidents_queryset = Incident.objects.filter(
            id__in=incident_ids_to_update
        ).select_related(  # Используется для ForeignKey
            'incident_type',
        ).prefetch_related(  # Используется для ManyToManyField
            'statuses'
        ).annotate(
            latest_status_date=Subquery(latest_status_subquery)
        )

        incidents_dict = {
            incident.pk: incident for incident in incidents_queryset
        }

        incidents_to_mark_finished = set()
        incidents_to_add_status = set()
        total = len(database_ids_with_issues)

        for database_id, issue in database_ids_with_issues:
            incident = incidents_dict.get(database_id)

            if not incident:
                continue

            is_sla_expired = issue.get(
                yt_manager.is_sla_expired_global_field_id)
            valid_is_sla_expired = yt_manager.get_sla_status(incident)

            if is_sla_expired != valid_is_sla_expired:
                yt_manager.update_issue_sla_status(issue, incident)

            if not incident.is_incident_finish:
                incidents_to_mark_finished.add(database_id)

            if not incident.statuses.filter(id=default_end_status.pk).exists():
                incidents_to_add_status.add(incident)

        if incidents_to_mark_finished:
            Incident.objects.filter(id__in=incidents_to_mark_finished).update(
                is_incident_finish=True
            )
            yt_managment_logger.info(
                f'Закрыто {len(incidents_to_mark_finished)} инцидента(ов)'
            )

        if incidents_to_add_status:
            with transaction.atomic():
                for incident in incidents_to_add_status:
                    incident.statuses.add(default_end_status)
