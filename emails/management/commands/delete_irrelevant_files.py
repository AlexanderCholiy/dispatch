import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
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
)


class Command(BaseCommand):
    help = (
        'Удаление старых вложений писем для закрытых инцидентов, а также '
        'старых писем без инцидента'
    )

    def handle(self, *args, **kwargs):
        self._remove_old_attachments_with_closed_incident()

    def _remove_old_attachments_with_closed_incident(self):
        """
        Удаляем EmailAttachment, EmailInTextAttachment, EmailMime если:

        - нет инцидента и пиьсмо пришло раньше вчерашнего дня;
        - есть инцидент, он закрыт и с момента закрытия прошло больше N дней.
        """
        threshold_for_incident = (
            timezone.now() - dt.timedelta(days=MAX_EMAILS_ATTACHMENT_DAYS)
        )
        threshold_for_email = (
            timezone.now() - dt.timedelta(days=1)
        )

        attachment_models: list[
            EmailAttachment | EmailInTextAttachment | EmailMime
        ] = [EmailAttachment, EmailInTextAttachment, EmailMime]

        for model in attachment_models:
            qs = (
                model.objects
                .filter(
                    Q(
                        email_msg__email_incident__isnull=True,
                        email_msg__email_date__lt=threshold_for_email,
                    )
                    | Q(
                        email_msg__email_incident__is_incident_finish=True,
                        email_msg__email_incident__update_date__lt=(
                            threshold_for_incident
                        ),
                    )
                )
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
