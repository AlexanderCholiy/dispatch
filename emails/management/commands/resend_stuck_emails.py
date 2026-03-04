from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.loggers import celery_logger
from emails.constants import MAX_STACK_EMAILS_TTL, MIN_STACK_EMAILS_TTL
from emails.models import EmailMessage, EmailStatus, EmailFolder
from emails.tasks import send_incident_email_task


class Command(BaseCommand):
    help = 'Повторная отправка "зависших" писем'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-seconds',
            type=int,
            default=MIN_STACK_EMAILS_TTL,
            help='Минимальный возраст письма в минутах',
        )
        parser.add_argument(
            '--max-seconds',
            type=int,
            default=MAX_STACK_EMAILS_TTL,
            help='Максимальный возраст письма в минутах',
        )

    def handle(self, *args, **options):
        min_seconds = options['min_seconds']
        max_seconds = options['max_seconds']

        folder = EmailFolder.objects.get(name='SENT')

        now = timezone.now()

        min_time = now - timedelta(seconds=min_seconds)
        max_time = now - timedelta(seconds=max_seconds)

        qs = (
            EmailMessage.objects
            .filter(
                email_date__lte=min_time,
                email_date__gte=max_time,
                folder=folder,
                is_email_from_yandex_tracker=False,
            )
            .exclude(
                status__in=[
                    EmailStatus.SENT,
                    EmailStatus.FAILED,
                ]
            )
        )

        total = qs.count()

        if total:
            celery_logger.warning(
                f'Найдено {total} писем для повторной отправки'
            )

        for email in qs.iterator():
            send_incident_email_task.delay(email.id)
