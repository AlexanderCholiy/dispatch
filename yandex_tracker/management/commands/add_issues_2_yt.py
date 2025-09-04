import time

from django.core.management.base import BaseCommand
from django.db import transaction

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.wraps import min_wait_timer, timer
from incidents.utils import IncidentManager
from emails.models import EmailMessage
from yandex_tracker.utils import YandexTrackerManager, yt_manager

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

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
                total_operations, error_count = self.add_issues_2_yt(
                    yt_manager)
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

    @min_wait_timer(yt_managment_logger)
    @timer(yt_managment_logger)
    def add_issues_2_yt(self, yt_manager: YandexTrackerManager):
        emails = YandexTrackerManager.emails_for_yandex_tracker()
        previous_incident = None
        total = len(emails)

        error_count = 0

        for index, email in enumerate(emails):
            PrettyPrint().progress_bar_info(
                index, total, 'Обновление заявок в YandexTracker:'
            )
            incident = email.email_incident
            with transaction.atomic():
                if not incident.responsible_user:
                    incident.responsible_user = (
                        IncidentManager
                        .choice_dispatch_for_incident(yt_manager)
                    )
                    incident.save()

                try:
                    if incident != previous_incident and email.is_first_email:
                        previous_incident = email.email_incident
                        yt_manager.add_incident_to_yandex_tracker(email, True)
                    else:
                        yt_manager.add_incident_to_yandex_tracker(email, False)
                except KeyboardInterrupt:
                    return
                except Exception as e:
                    error_count += 1
                    yt_managment_logger.exception(e)
                else:
                    email.was_added_2_yandex_tracker = True
                    email.save()

        return total, error_count
