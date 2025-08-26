import os

from django.core.management.base import BaseCommand
from django.db import models

from yandex_tracker.utils import YandexTrackerManager
from core.constants import YANDEX_TRACKER_ROTATING_FILE
from core.loggers import LoggerFactory
from core.wraps import timer
from incidents.models import Incident
from emails.models import EmailMessage


yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

    @timer(yt_managment_logger)
    def handle(self, *args, **kwargs):
        result = YandexTrackerManager(
            os.getenv('YT_CLIENT_ID'),
            os.getenv('YT_CLIENT_SECRET'),
            os.getenv('YT_ACCESS_TOKEN'),
            os.getenv('YT_REFRESH_TOKEN'),
            os.getenv('YT_ORGANIZATION_ID'),
            os.getenv('YT_QUEUE'),
            os.getenv('YT_DATABASE_ID_GLOBAL_FIELD_NAME'),

        )
        emails = self.emails_for_yandex_tracker
        for email in emails:
            print(email)

    @property
    def emails_for_yandex_tracker(self) -> models.QuerySet[EmailMessage]:
        return EmailMessage.objects.filter(
            is_email_from_yandex_tracker=False,
            was_added_2_yandex_tracker=False,
            email_incident__isnull=False,
            email_incident__pole__isnull=False,
        )
