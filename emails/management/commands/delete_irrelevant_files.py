import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.loggers import incident_logger
from core.pretty_print import PrettyPrint
from emails.constants import (
    EMAILS_FILES_2_DEL_BATCH_SIZE,
    MAX_EMAILS_ATTACHMENT_DAYS,
)
from emails.models import (
    EmailAttachment,
    EmailInTextAttachment,
    EmailMime,
    Incident,
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
            qs = model.objects.select_related(
                'email_msg', 'email_msg__email_incident'
            )
            total = qs.count()
            to_delete_ids: list[int] = []
            deleted_count = 0

            for index, attachment in enumerate(
                qs.iterator(chunk_size=EMAILS_FILES_2_DEL_BATCH_SIZE)
            ):
                PrettyPrint.progress_bar_debug(
                    index, total,
                    f'Проверка старых вложений ({model.__name__}):'
                )

                email = attachment.email_msg
                incident: Incident | None = getattr(
                    email, 'email_incident', None
                )

                if not incident or not incident.is_incident_finish:
                    continue
                if (
                    incident.update_date and incident.update_date >= threshold
                ):
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

                to_delete_ids.append(attachment.id)

                if len(to_delete_ids) >= EMAILS_FILES_2_DEL_BATCH_SIZE:
                    model.objects.filter(id__in=to_delete_ids).delete()
                    to_delete_ids.clear()

            # удалить хвост
            if to_delete_ids:
                model.objects.filter(id__in=to_delete_ids).delete()

            if deleted_count:
                incident_logger.info(
                    f'Удалено {deleted_count} неактуальных вложений '
                    f'для модели {model.__name__}'
                )
