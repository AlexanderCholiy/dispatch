from django.core.management.base import BaseCommand
from django.utils import timezone
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import default_logger
from emails.constants import (
    CLEANUP_EMAILS_WITHOUT_INCIDENT_TTL,
    EMAILS_BATCH_SIZE,
)
from emails.models import EmailMessage


class Command(BaseCommand):
    help = 'Удаляет старые письма не привязанных к инциденту'

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - CLEANUP_EMAILS_WITHOUT_INCIDENT_TTL

        queryset = EmailMessage.objects.filter(
            email_incident__isnull=True,
            email_date__lt=cutoff_date
        )

        total_count = queryset.count()

        if total_count == 0:
            default_logger.debug('Нет писем для удаления.')
            return

        deleted_count = 0

        with tqdm(
            total=total_count,
            desc='Удаление старых писем без инцидента',
            colour='yellow',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:

            current_batch = []

            for pk in (
                queryset.values_list('pk', flat=True)
                .iterator(chunk_size=EMAILS_BATCH_SIZE)
            ):
                current_batch.append(pk)

                if len(current_batch) >= EMAILS_BATCH_SIZE:
                    count = EmailMessage.objects.filter(
                        pk__in=current_batch,
                        email_incident__isnull=True,
                    ).count()
                    EmailMessage.objects.filter(
                        pk__in=current_batch,
                        email_incident__isnull=True,
                    ).delete()

                    deleted_count += count
                    pbar.update(len(current_batch))
                    current_batch = []

            if current_batch:
                count = EmailMessage.objects.filter(
                    pk__in=current_batch,
                    email_incident__isnull=True,
                ).count()
                EmailMessage.objects.filter(
                    pk__in=current_batch,
                    email_incident__isnull=True,
                ).delete()
                deleted_count += count
                pbar.update(len(current_batch))

        default_logger.info(
            f'Удалено {deleted_count} старых писем без инцидента.'
        )
