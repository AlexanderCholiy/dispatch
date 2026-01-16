import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.constants import EMAIL_MIME_DIR, INCIDENT_DIR, SUBFOLDER_DATE_FORMAT
from core.loggers import email_parser_logger
from core.pretty_print import PrettyPrint
from core.wraps import timer
from emails.constants import EMAILS_FILES_2_DEL_BATCH_SIZE
from emails.models import EmailAttachment, EmailInTextAttachment, EmailMime


class Command(BaseCommand):
    help = 'Удаление вложений без файла или без записи и пустых папок.'

    @timer(email_parser_logger)
    def handle(self, *args, **kwargs):
        now = timezone.now()
        threshold = now - dt.timedelta(days=1)

        attachment_dirs = {
            'attachments': Path(INCIDENT_DIR),
            'mimes': Path(EMAIL_MIME_DIR)
        }

        for _, directory in attachment_dirs.items():
            if not directory.exists():
                email_parser_logger.warning(
                    f'Папки {directory} не существует.'
                )
                continue

            # Шаг 1: удалить пустые файлы
            self._remove_empty_files(directory)

            # Шаг 2: удалить старые файлы без записи
            self._remove_files_without_db_record(directory, threshold)

            # Шаг 3: удалить пустые подпапки старше 1 дня
            self._remove_old_empty_dirs(directory, now)

        # Шаг 4: удалить записи без файлов
        self._remove_db_records_without_files()

    def _remove_empty_files(self, directory: Path):
        all_dirs = [p for p in directory.rglob('*') if p.is_file()]

        deleted_count = 0
        total = len(all_dirs)

        for index, file_path in enumerate(all_dirs):
            PrettyPrint.progress_bar_debug(
                index, total, f'Удаление пустых файлов ({directory.name}):'
            )

            try:
                if file_path.stat().st_size == 0:
                    file_path.unlink()
                    deleted_count += 1
            except OSError:
                email_parser_logger.warning(
                    f'Не удалось удалить пустой файл: {file_path}'
                )

        if deleted_count:
            email_parser_logger.info(
                f'Удалено {deleted_count} пустых файлов в {directory}'
            )

    def _remove_files_without_db_record(
        self, directory: Path, threshold: dt.datetime
    ):
        valid_files = set(
            list(EmailAttachment.objects.values_list('file_url', flat=True))
            + list(
                EmailInTextAttachment.objects
                .values_list('file_url', flat=True)
            )
            + list(EmailMime.objects.values_list('file_url', flat=True))
        )
        all_dirs = [p for p in directory.rglob('*') if p.is_file()]

        deleted_count = 0
        total = len(all_dirs)

        for index, file_path in enumerate(all_dirs):
            PrettyPrint.progress_bar_info(
                index, total,
                f'Проверка файлов без записи в базе ({directory.name}):'
            )

            relative_path = str(file_path.relative_to(settings.MEDIA_ROOT))

            try:
                mtime = dt.datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.get_current_timezone()
                )
            except OSError:
                continue

            # Если нет записи в базе и файл старше threshold — удаляем
            if relative_path not in valid_files and mtime < threshold:
                try:
                    file_path.unlink()
                    deleted_count += 1

                except OSError:
                    email_parser_logger.warning(
                        f'Не удалось удалить файл {file_path}'
                    )

        if deleted_count:
            email_parser_logger.info(
                f'Удалено {deleted_count} файлов без записи в {directory}'
            )

    def _remove_old_empty_dirs(self, directory: Path, now: dt.datetime):
        all_dirs = [p for p in directory.rglob('*') if p.is_dir()]
        all_dirs.sort(key=lambda p: -len(p.parts))

        total = len(all_dirs)
        deleted_count = 0

        for index, dir_path in enumerate(all_dirs):
            PrettyPrint.progress_bar_error(
                index, total, f'Удаление пустых подпапок ({directory.name}):'
            )

            try:
                if not any(dir_path.iterdir()):
                    folder_name = dir_path.name
                    try:
                        folder_date = timezone.make_aware(
                            dt.datetime.strptime(
                                folder_name, SUBFOLDER_DATE_FORMAT
                            ),
                            timezone.get_current_timezone()
                        )
                    except ValueError:
                        folder_date = None

                    if (
                        folder_date is None
                        or folder_date < now - dt.timedelta(days=1)
                    ):
                        dir_path.rmdir()
                        deleted_count += 1

            except OSError:
                email_parser_logger.warning(
                    f'Не удалось удалить папку {dir_path}'
                )

        if deleted_count:
            email_parser_logger.info(
                f'Удалено {deleted_count} пустых подпапок в {directory}'
            )

    def _remove_db_records_without_files(self):
        models: list[EmailAttachment | EmailInTextAttachment | EmailMime] = [
            EmailAttachment, EmailInTextAttachment, EmailMime
        ]
        for model in models:
            qs = model.objects.all()

            total = qs.count()
            to_delete_ids: list[int] = []
            deleted_count = 0

            for index, attachment in enumerate(
                qs.iterator(chunk_size=EMAILS_FILES_2_DEL_BATCH_SIZE)
            ):
                PrettyPrint.progress_bar_warning(
                    index,
                    total,
                    f'Проверка записей без файлов ({model.__name__}):'
                )

                file_path = (
                    Path(settings.MEDIA_ROOT) / attachment.file_url.name
                )

                if not file_path.exists():
                    to_delete_ids.append(attachment.id)
                    deleted_count += 1

                # удаляем батч
                if len(to_delete_ids) >= EMAILS_FILES_2_DEL_BATCH_SIZE:
                    model.objects.filter(id__in=to_delete_ids).delete()
                    to_delete_ids.clear()

            # удалить хвост
            if to_delete_ids:
                model.objects.filter(id__in=to_delete_ids).delete()

            if deleted_count:
                email_parser_logger.info(
                    f'Удалено {deleted_count} записей без файлов для '
                    f'{model.__name__}'
                )
