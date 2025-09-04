import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.constants import (
    EMAIL_LOG_ROTATING_FILE,
    INCIDENT_DIR,
    SUBFOLDER_DATE_FORMAT,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.wraps import timer
from emails.constants import MAX_EMAILS_ATTACHMENT_DAYS
from emails.models import EmailAttachment, EmailInTextAttachment, EmailMessage
from emails.utils import EmailManager

email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'

    def _remove_unknown_files(
        self, file_path: Path, valid_files: set[Path], threshold: dt.datetime
    ):
        if file_path.is_file():
            relative_path = str(file_path.relative_to(settings.MEDIA_ROOT))

            if relative_path not in valid_files:
                try:
                    mtime = dt.datetime.fromtimestamp(
                        file_path.stat().st_mtime)
                except OSError:
                    email_managment_logger.warning(
                        'Не удалось получить время модификации '
                        f'{file_path}'
                    )
                    return

                if mtime < threshold:
                    try:
                        file_path.unlink()
                    except OSError:
                        email_managment_logger.warning(
                            f'Не удалось удалить {file_path}')

    @timer(email_managment_logger)
    def handle(self, *args, **kwargs):
        tg_manager.send_startup_notification(__name__)

        attachment_dir = Path(INCIDENT_DIR)
        if not attachment_dir.exists():
            email_managment_logger.warning(
                f'Папки {attachment_dir} не существует.')
            return

        valid_attachment_files = set(
            EmailAttachment.objects.values_list('file_url', flat=True)
        )
        valid_intext_attachment_files = set(
            EmailInTextAttachment.objects.values_list('file_url', flat=True)
        )

        valid_files = valid_attachment_files.union(
            valid_intext_attachment_files)

        now = timezone.now()
        threshold = now - dt.timedelta(days=max(MAX_EMAILS_ATTACHMENT_DAYS, 0))
        total = sum(1 for _ in attachment_dir.rglob('*'))

        for index, file_path in enumerate(attachment_dir.rglob('*')):
            PrettyPrint.progress_bar_debug(
                index, total,
                'Удаление старых файлов без записи в базе:'
            )
            self._remove_unknown_files(file_path, valid_files, threshold)

        total = sum(1 for _ in attachment_dir.rglob('*'))
        for index, dir_path in enumerate(sorted(
            attachment_dir.rglob('*'), key=lambda p: -p.parts.__len__()
        )):
            PrettyPrint.progress_bar_info(
                index, total,
                'Удаление пустых папок для вложений:'
            )
            if dir_path.is_dir():
                try:
                    if not any(dir_path.iterdir()):
                        folder_name = dir_path.name
                        folder_date = dt.datetime.strptime(
                            folder_name, SUBFOLDER_DATE_FORMAT)
                        if folder_date < threshold:
                            dir_path.rmdir()
                except OSError:
                    email_managment_logger.warning(
                        f'Не удалось удалить папку {dir_path}.')
                except ValueError:
                    continue

        emails = EmailMessage.objects.filter(email_date__lt=threshold)
        total = len(emails)
        for index, email in enumerate(emails):
            PrettyPrint.progress_bar_error(
                index, total,
                'Удаление записей вложений без файла:'
            )
            EmailManager.get_email_attachments(email)

        tg_manager.send_success_notification(__name__)
