import os
import time

from django.core.management.base import BaseCommand
from django.db import transaction

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.wraps import min_wait_timer, timer
from incidents.utils import IncidentManager
from yandex_tracker.utils import YandexTrackerManager

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

    @timer(yt_managment_logger)
    def handle(self, *args, **kwargs):
        yt_manager = YandexTrackerManager(
            os.getenv('YT_CLIENT_ID'),
            os.getenv('YT_CLIENT_SECRET'),
            os.getenv('YT_ACCESS_TOKEN'),
            os.getenv('YT_REFRESH_TOKEN'),
            os.getenv('YT_ORGANIZATION_ID'),
            os.getenv('YT_QUEUE'),
            os.getenv('YT_DATABASE_GLOBAL_FIELD_ID'),
            os.getenv('YT_POLE_NUMBER_GLOBAL_FIELD_ID'),
            os.getenv('YT_BASE_STATION_GLOBAL_FIELD_ID'),
            os.getenv('YT_EMAIL_DATETIME_GLOBAL_FIELD_ID'),
            os.getenv('IS_NEW_MSG_GLOBAL_FIELD_ID'),
        )

        while True:
            try:
                self.add_issues_2_yt(yt_manager)
            except KeyboardInterrupt:
                return
            except Exception as e:
                yt_managment_logger.critical(e, exc_info=True)
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)

    @min_wait_timer(yt_managment_logger)
    @timer(yt_managment_logger)
    def add_issues_2_yt(self, yt_manager: YandexTrackerManager):
        emails = YandexTrackerManager.emails_for_yandex_tracker()
        previous_incident = None
        total = len(emails)

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
                    yt_managment_logger.exception(e)
                else:
                    email.was_added_2_yandex_tracker = True
                    email.save()
