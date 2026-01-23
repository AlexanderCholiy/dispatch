import datetime as dt
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.loggers import default_logger
from core.pretty_print import PrettyPrint
from core.wraps import timer
from users.constants import SUBFOLDER_AVATAR_DIR

User = get_user_model()


class Command(BaseCommand):
    help = 'Удаление файлов аватаров на диске, которых нет в базе данных.'
    dt = dt.timedelta(days=1)

    @timer(default_logger)
    def handle(self, *args, **kwargs):
        self.avatar_dir = Path(settings.MEDIA_ROOT) / SUBFOLDER_AVATAR_DIR

        # Шаг 1: удалить старые файлы без записи
        self._remove_files_without_db_record()

        # Шаг 2: удалить записи без файлов
        self._remove_db_records_without_files()

    def _remove_files_without_db_record(self):
        """
        Удаляет файлы с диска, если на них нет ссылки в БД и они старше порога.
        """
        threshold = timezone.now() - self.dt

        if not self.avatar_dir.exists():
            default_logger.warning(
                f'Папка аватаров {self.avatar_dir} не найдена.'
            )
            return

        valid_avatars = set(
            User.objects.exclude(avatar__isnull=True)
            .values_list('avatar', flat=True)
        )
        all_files = [p for p in self.avatar_dir.rglob('*') if p.is_file()]

        total = len(all_files)
        deleted_count = 0

        for index, file_path in enumerate(all_files):
            PrettyPrint.progress_bar_debug(
                index, total, 'Проверка аватаров без записи в базе:'
            )

            relative_path = str(file_path.relative_to(settings.MEDIA_ROOT))

            try:
                mtime = dt.datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.get_current_timezone()
                )
            except OSError:
                continue

            if relative_path not in valid_avatars and mtime < threshold:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except OSError:
                    default_logger.warning(
                        f'Не удалось удалить аватар: {file_path}'
                    )

        if deleted_count:
            default_logger.info(
                f'Удалено {deleted_count} неиспользуемых файлов аватаров.'
            )

    def _remove_db_records_without_files(self):
        """
        Удаляет записи из базы данных, если физический файл на диске
        отсутствует.
        """
        threshold = timezone.now() - self.dt
        qs = User.objects.exclude(avatar__isnull=True).filter(
            date_joined__lt=threshold
        )

        total = qs.count()
        fixed_count = 0

        for index, user in enumerate(qs.iterator()):
            PrettyPrint.progress_bar_warning(
                index, total, 'Проверка аватаров без файлов:'
            )

            file_path: Path = Path(settings.MEDIA_ROOT) / user.avatar.name

            if not file_path.exists():
                user.avatar = None
                user.save(update_fields=['avatar'])
                fixed_count += 1

        if fixed_count:
            default_logger.info(
                f'Исправлено {fixed_count} записей User с отсутствующими '
                'файлами аватаров.'
            )
