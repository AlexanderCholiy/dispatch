import os

from django.core.management.base import BaseCommand
from django.db import models, transaction
from requests.exceptions import RequestException

from yandex_tracker.utils import YandexTrackerManager
from core.constants import YANDEX_TRACKER_ROTATING_FILE, API_STATUS_EXCEPTIONS
from core.loggers import LoggerFactory
from core.wraps import timer
from incidents.models import Incident
from incidents.utils import IncidentManager
from emails.models import EmailMessage
from emails.utils import EmailManager
from core.pretty_print import PrettyPrint
from core.exceptions import ApiServerError, ApiTooManyRequests
from yandex_tracker.exceptions import YandexTrackerAuthErr


yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

    @timer(yt_managment_logger)
    @transaction.atomic()
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

        emails = YandexTrackerManager.emails_for_yandex_tracker()
        previous_incident = None
        total = len(emails)

        for index, email in enumerate(emails):
            PrettyPrint.progress_bar_info(
                index, total, 'Обновление заявок в YandexTracker:'
            )
            incident = email.email_incident
            if not incident.responsible_user:
                incident.responsible_user = (
                    IncidentManager.choice_dispatch_for_incident(yt_manager)
                )
                incident.save()
            r = None
            try:
                if incident != previous_incident and email.is_first_email:
                    previous_incident = email.email_incident
                    r = yt_manager.add_incident_to_yandex_tracker(email, True)
                else:
                    r = yt_manager.add_incident_to_yandex_tracker(email, False)
            except (
                RequestException,
                ApiTooManyRequests,
                ApiServerError,
                YandexTrackerAuthErr,
            ):
                pass
            except tuple(API_STATUS_EXCEPTIONS.values()):
                pass
            except KeyboardInterrupt:
                raise
            except Exception as e:
                yt_managment_logger.exception(e)
            else:
                if r:
                    email.was_added_2_yandex_tracker = True
                    email.save()
