import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.pretty_print import PrettyPrint
from core.loggers import incident_logger
from emails.constants import MAX_EMAILS_ATTACHMENT_DAYS
from emails.models import (
    EmailAttachment, EmailInTextAttachment, EmailMime, Incident
)


class Command(BaseCommand):
    help = 'Удаление старых вложений писем для закрытых инцидентов.'

    def handle(self, *args, **kwargs):
        self._remove_old_attachments_with_closed_incident()

    def _remove_old_attachments_with_closed_incident(self):
        """
        Удаляем EmailAttachment, EmailInTextAttachment, EmailMime,
        если у письма есть закрытый инцидент, и дата закрытия
        старше MAX_EMAILS_ATTACHMENT_DAYS.
        """
        threshold = (
            timezone.now() - dt.timedelta(days=MAX_EMAILS_ATTACHMENT_DAYS)
        )
        attachment_models: list[
            EmailAttachment | EmailInTextAttachment | EmailMime
        ] = [EmailAttachment, EmailInTextAttachment, EmailMime]

        for model in attachment_models:
            queryset = model.objects.select_related(
                'email_msg', 'email_msg__email_incident'
            )
            total = queryset.count()
            deleted_count = 0

            for index, attachment in enumerate(queryset):
                PrettyPrint.progress_bar_info(
                    index, total,
                    f'Проверка старых вложений ({model.__name__}):'
                )

                email = attachment.email_msg
                incident: Incident = getattr(email, 'email_incident', None)

                if not incident or not incident.is_incident_finish:
                    continue
                if (
                    incident.is_incident_finish and incident.update_date
                ) >= threshold:
                    continue

                file_path = (
                    Path(settings.MEDIA_ROOT) / attachment.file_url.name
                )

                try:
                    if file_path.exists():
                        file_path.unlink()
                        deleted_count += 1
                except OSError:
                    incident_logger.warning(
                        f'Не удалось удалить файл {file_path} для '
                        f'{model.__name__}'
                    )

                attachment.delete()

            if deleted_count:
                incident_logger.info(
                    f'Удалено {deleted_count} неактуальных вложений '
                    f'для модели {model.__name__}'
                )
