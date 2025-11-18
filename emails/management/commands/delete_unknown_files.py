import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.constants import (
    EMAIL_LOG_ROTATING_FILE,
    EMAIL_MIME_DIR,
    INCIDENT_DIR,
    SUBFOLDER_DATE_FORMAT,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.wraps import timer
from emails.constants import MAX_EMAILS_ATTACHMENT_DAYS
from emails.models import (
    EmailAttachment,
    EmailInTextAttachment,
    EmailMessage,
    EmailMime
)
from emails.utils import EmailManager

email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE
).get_logger()


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'

    def _remove_unknown_files(
        self, file_path: Path, valid_files: set[Path], threshold: dt.datetime
    ):
        if not file_path.is_file():
            return

        # Сразу удаляем пустые файлы:
        try:
            size = file_path.stat().st_size
        except OSError:
            email_managment_logger.warning(
                f'Не удалось получить размер файла {file_path}'
            )
            return

        if size == 0:
            try:
                file_path.unlink()
                email_managment_logger.info(
                    f'Удалён пустой файл вложения: {file_path}'
                )
            except OSError:
                email_managment_logger.warning(
                    f'Не удалось удалить пустой файл {file_path}'
                )
            return

        # Проверяем, есть ли файл в базе:
        relative_path = str(file_path.relative_to(settings.MEDIA_ROOT))

        if relative_path not in valid_files:
            try:
                mtime = dt.datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.get_current_timezone()
                )
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
        mime_dir = Path(EMAIL_MIME_DIR)
        if not attachment_dir.exists():
            email_managment_logger.warning(
                f'Папки {attachment_dir} не существует.')
            return

        if not mime_dir.exists():
            email_managment_logger.warning(
                f'Папки {mime_dir} не существует.')
            return

        valid_attachment_files = set(
            EmailAttachment.objects.values_list('file_url', flat=True)
        )
        valid_intext_attachment_files = set(
            EmailInTextAttachment.objects.values_list('file_url', flat=True)
        )
        valid_mime_files = set(
            EmailMime.objects.values_list('file_url', flat=True)
        )

        valid_files = valid_attachment_files.union(
            valid_intext_attachment_files, valid_mime_files
        )

        now = timezone.now()
        threshold = now - dt.timedelta(days=max(MAX_EMAILS_ATTACHMENT_DAYS, 0))
        total = sum(1 for _ in attachment_dir.rglob('*'))

        for index, file_path in enumerate(attachment_dir.rglob('*')):
            PrettyPrint.progress_bar_debug(
                index, total,
                'Удаление старых вложений без записи в базе:'
            )
            self._remove_unknown_files(file_path, valid_files, threshold)

        for index, file_path in enumerate(mime_dir.rglob('*')):
            PrettyPrint.progress_bar_debug(
                index, total,
                'Удаление старых mime файлов без записи в базе:'
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
                        folder_date = timezone.make_aware(
                            dt.datetime.strptime(
                                folder_name, SUBFOLDER_DATE_FORMAT),
                            timezone.get_current_timezone()
                        )
                        if folder_date < now - dt.timedelta(days=1):
                            dir_path.rmdir()
                except OSError:
                    email_managment_logger.warning(
                        f'Не удалось удалить папку {dir_path}.')
                except ValueError:
                    continue

        total = sum(1 for _ in mime_dir.rglob('*'))
        for index, dir_path in enumerate(sorted(
            mime_dir.rglob('*'), key=lambda p: -p.parts.__len__()
        )):
            PrettyPrint.progress_bar_info(
                index, total,
                'Удаление пустых папок для mime файлов:'
            )
            if dir_path.is_dir():
                try:
                    if not any(dir_path.iterdir()):
                        folder_name = dir_path.name
                        folder_date = timezone.make_aware(
                            dt.datetime.strptime(
                                folder_name, SUBFOLDER_DATE_FORMAT),
                            timezone.get_current_timezone()
                        )
                        if folder_date < now - dt.timedelta(days=1):
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
            EmailManager.get_email_mimes(email)

        self._remove_orphan_attachments()

        tg_manager.send_success_notification(__name__)

    def _remove_orphan_attachments(self):
        attachments_to_delete = []
        attachments = EmailAttachment.objects.all()
        total = len(attachments)

        for index, attachment in enumerate(attachments):
            PrettyPrint.progress_bar_error(
                index, total,
                'Проверка записей, без файла в базе для EmailAttachment:'
            )

            file_path = Path(settings.MEDIA_ROOT) / attachment.file_url.name
            if not file_path.exists():
                attachments_to_delete.append(attachment.id)

        intext_to_delete = []
        intexts = EmailInTextAttachment.objects.all()
        total = len(intexts)

        for index, attachment in enumerate(intexts):
            PrettyPrint.progress_bar_warning(
                index, total,
                'Проверка записей, без файла в базе для EmailInTextAttachment:'
            )

            file_path = Path(settings.MEDIA_ROOT) / attachment.file_url.name
            if not file_path.exists():
                intext_to_delete.append(attachment.id)

        mime_to_delete = []
        mimes = EmailMime.objects.all()
        total = len(mimes)

        for index, attachment in enumerate(mimes):
            PrettyPrint.progress_bar_success(
                index, total,
                'Проверка записей, без файла в базе для EmailMime:'
            )

            file_path = Path(settings.MEDIA_ROOT) / attachment.file_url.name
            if not file_path.exists():
                mime_to_delete.append(attachment.id)

        if attachments_to_delete:
            email_managment_logger.info(
                f'Удаляем {len(attachments_to_delete)} записей '
                'EmailAttachment без файлов'
            )
            EmailAttachment.objects.filter(
                id__in=attachments_to_delete
            ).delete()

        if intext_to_delete:
            email_managment_logger.info(
                f'Удаляем {len(intext_to_delete)} записей '
                'EmailInTextAttachment без файлов'
            )
            EmailInTextAttachment.objects.filter(
                id__in=intext_to_delete
            ).delete()

        if mime_to_delete:
            email_managment_logger.info(
                f'Удаляем {len(mime_to_delete)} записей EmailMime без файлов'
            )
            EmailMime.objects.filter(id__in=mime_to_delete).delete()
