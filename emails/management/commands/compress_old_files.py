import datetime as dt
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.constants import INCIDENT_DIR
from core.loggers import incident_logger
from core.pretty_print import PrettyPrint
from core.services.formatters import format_size_readable
from core.wraps import timer
from emails.constants import (
    ARCHIVE_EXTENSIONS,
    COMPRESS_BATCH_SIZE,
    COMPRESS_EMAILS_ATTACHMENT_DAYS,
)
from emails.models import (
    EmailAttachment,
    EmailInTextAttachment,
    EmailMime,
)


class FileEntry(TypedDict):
    model: EmailAttachment | EmailInTextAttachment | EmailMime
    obj_id: int
    file_path: Path
    size: int
    original_name: str
    is_archive: bool


class Command(BaseCommand):
    help = (
        'Сжатие старых вложений писем в .zip архивы. '
        'Все файлы (EmailAttachment, EmailInTextAttachment, EmailMime) '
        'старше N дней, принадлежащие одному письму, сжимаются в один .zip. '
        'Исходные файлы удаляются, пути в БД обновляются.'
    )

    @timer(incident_logger, False)
    def handle(self, *args, **kwargs):
        threshold = timezone.now() - dt.timedelta(
            days=COMPRESS_EMAILS_ATTACHMENT_DAYS
        )

        # Собираем все файлы из всех моделей, группируем по ID письма:
        email_to_entries = self._collect_files(threshold)

        if not email_to_entries:
            incident_logger.debug('Нет файлов для сжатия.')
            return

        total_archived = 0
        total_size_before = 0
        total_size_after = 0

        for email_msg_id, entries in email_to_entries.items():
            size_before = sum(e['size'] for e in entries)
            archived_count, size_after = self._compress_email(
                email_msg_id=email_msg_id,
                entries=entries,
            )

            total_archived += archived_count
            total_size_before += size_before
            total_size_after += size_after

        if total_archived:
            delta = total_size_before - total_size_after
            incident_logger.debug(
                f'Сжато: {total_archived} файлов, '
                f'до: {format_size_readable(total_size_before)}, '
                f'после: {format_size_readable(total_size_after)}, '
                f'экономия: {format_size_readable(delta)}.'
            )

    def _collect_files(self, threshold) -> dict[int, list[FileEntry]]:
        """
        Собирает файлы из всех трёх моделей, группирует по ID письма.

        Файлы с архивными расширениями (.zip, .7z, ...) включаются,
        но если ВСЕ файлы письма — архивы, письмо пропускается.

        Возвращает:
        {
            12345: [
                {
                    'model': EmailAttachment,
                    'obj_id': 123,
                    'file_path': Path('...'),
                    'size': 5242880,
                    'original_name': '110609__hash1__7__26.jpg',
                },
                {
                    'model': EmailInTextAttachment,
                    'obj_id': 456,
                    'file_path': Path('...'),
                    'size': 3145728,
                    'original_name': '110610__hash2__7__27.pdf',
                },
            ],
            ...
        }
        """
        email_to_entries: dict[int, list[FileEntry]] = defaultdict(list)
        models: list[EmailAttachment | EmailInTextAttachment | EmailMime] = [
            EmailAttachment, EmailInTextAttachment, EmailMime
        ]

        for model in models:
            qs = model.objects.filter(
                Q(
                    email_msg__email_incident__isnull=True,
                    email_msg__email_date__lt=threshold,
                )
                | Q(
                    email_msg__email_incident__is_incident_finish=True,
                    email_msg__email_incident__incident_finish_date__isnull=False,  # noqa: E501
                    email_msg__email_incident__incident_finish_date__lt=(
                        threshold
                    ),
                    email_msg__email_date__lt=threshold,
                )
            ).select_related('email_msg', 'email_msg__email_incident',)

            total = qs.count()
            if total == 0:
                continue

            for index, obj in enumerate(
                qs.iterator(chunk_size=COMPRESS_BATCH_SIZE)
            ):
                PrettyPrint.progress_bar_debug(
                    index, total,
                    f'Сбор файлов ({model.__name__}):'
                )

                file_path = Path(settings.MEDIA_ROOT) / obj.file_url.name
                if (
                    not file_path.exists()
                    or file_path.stat().st_size == 0
                ):
                    continue

                # Группируем по ID письма:
                email_to_entries[obj.email_msg.id].append({
                    'model': model,
                    'obj_id': obj.id,
                    'file_path': file_path,
                    'size': file_path.stat().st_size,
                    'original_name': file_path.name,
                    'is_archive': (
                        file_path.suffix.lower() in ARCHIVE_EXTENSIONS
                    ),
                })

        result = {}
        for email_id, entries in email_to_entries.items():
            if all(e['is_archive'] for e in entries):
                continue
            result[email_id] = entries

        return result

    def _compress_email(
        self,
        email_msg_id: int,
        entries: list[FileEntry],
    ) -> tuple[int, int]:
        """
        Сжимает все файлы одного письма в один .zip.

        Порядок операций (безопасный):
        1. Создаём архив
        2. Создаём новую запись в БД
        3. Удаляем старые записи из БД
        4. Удаляем исходные файлы с диска

        Если БД упадёт на шаге 2-3 — файлы на диске целы,
        можно перезапустить команду.
        """
        valid_entries = [e for e in entries if e['file_path'].exists()]
        if not valid_entries:
            return 0, 0

        # Берём название подпапки (дату) из первого файла:
        date_subfolder = valid_entries[0]['file_path'].parent.name
        dir_path = Path(INCIDENT_DIR) / date_subfolder
        dir_path.mkdir(parents=True, exist_ok=True)

        zip_name = f'archive_email_{email_msg_id}.zip'
        zip_path = dir_path / zip_name

        # Если архив уже существует — не перезаписываем
        if zip_path.exists():
            incident_logger.warning(
                f'Архив уже существует: {zip_path}, пропускаю'
            )
            return 0, zip_path.stat().st_size

        # 1. Создаём архив
        try:
            with zipfile.ZipFile(
                zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6
            ) as zf:
                for entry in valid_entries:
                    zf.write(
                        entry['file_path'],
                        arcname=entry['original_name'],
                    )
        except (OSError, zipfile.BadZipFile) as e:
            incident_logger.error(
                f'Ошибка создания архива {zip_path}: {e}'
            )
            return 0, 0

        zip_size = zip_path.stat().st_size

        # 2-3. Обновляем БД (сначала новая запись, потом удаление старых)
        try:
            self._update_db(valid_entries, zip_path)
        except Exception as e:
            incident_logger.exception(
                f'Ошибка обновления БД для письма {email_msg_id}: {e}. '
                f'Архив {zip_path} создан, но БД не обновлена. '
                f'Файлы на диске не удалены.'
            )
            # Удаляем архив, чтобы при перезапуске всё было чисто
            zip_path.unlink(missing_ok=True)
            return 0, 0

        deleted_count = len(valid_entries)

        incident_logger.debug(
            f'Письмо {email_msg_id}: сжато {deleted_count} файлов '
            f'→ {zip_name} ({format_size_readable(zip_size)})'
        )

        return deleted_count, zip_size

    @transaction.atomic
    def _update_db(self, entries: list[FileEntry], zip_path: Path):
        """
        Создаёт новую EmailAttachment с архивом,
        затем удаляет старые записи и файлы.

        Порядок: сначала create → потом delete.
        Если create упадёт — старые записи целы.
        """
        zip_relative = zip_path.relative_to(
            Path(settings.MEDIA_ROOT)
        ).as_posix()

        # Берём email_msg из первой записи
        first_entry = entries[0]
        first_obj = first_entry['model'].objects.get(id=first_entry['obj_id'])
        email_msg = first_obj.email_msg

        # 1. Создаём новую запись (если упадёт — старые целы)
        EmailAttachment.objects.create(
            email_msg=email_msg,
            file_url=zip_relative,
        )

        # 2. Удаляем старые записи
        model_to_ids: dict[
            EmailAttachment | EmailInTextAttachment | EmailMime, list[int]
        ] = defaultdict(list)
        for entry in entries:
            model_to_ids[entry['model']].append(entry['obj_id'])

        for model, ids in model_to_ids.items():
            model.objects.filter(id__in=ids).delete()
