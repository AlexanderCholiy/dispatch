import csv
from datetime import datetime
from pathlib import Path

from django.db.models import Q, QuerySet
from django.utils import timezone

from api.constants import (
    ACTUAL_INCIDENTS_FILE,
    ACTUAL_INCIDENTS_TTL,
    ARCHIVE_INCIDENTS_DIR,
    ARCHIVE_INCIDENTS_TTL,
    INCIDENTS_CSV_CHUNK,
    INCIDENTS_DB_CHUNK,
)
from api.serializers.incidents import IncidentReportSerializer
from api.utils import get_first_day_prev_month, is_file_fresh
from api.views.incidents import IncidentReportViewSet
from core.loggers import default_logger
from core.wraps import timer


class IncidentsCsvBuilder:
    def __init__(self):
        self.view = IncidentReportViewSet()
        self._qs = None

    @property
    def qs(self) -> QuerySet:
        if self._qs is None:
            self._qs = self.view.get_queryset()
        return self._qs

    @staticmethod
    def _serialize_row(obj) -> dict:
        """Преобразует объект инцидента в словарь для CSV."""
        serializer = IncidentReportSerializer(obj)
        return serializer.data

    @staticmethod
    def _generate_csv_file(queryset: QuerySet, file_path: Path):
        """Генерирует CSV файл с потоковой записью."""
        tmp_file = file_path.with_suffix('.tmp')
        has_data = False

        try:
            with tmp_file.open('w', newline='', encoding='utf-8') as f:
                fieldnames = list(IncidentReportSerializer().fields.keys())

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                chunk = []

                for obj in queryset.iterator(chunk_size=INCIDENTS_DB_CHUNK):
                    row_data = IncidentsCsvBuilder._serialize_row(obj)
                    chunk.append(row_data)
                    has_data = True

                    # Пакетная запись каждые N строк:
                    if len(chunk) >= INCIDENTS_CSV_CHUNK:
                        writer.writerows(chunk)
                        chunk = []

                # Дописываем остаток:
                if chunk:
                    writer.writerows(chunk)

            if has_data:
                tmp_file.replace(file_path)
            else:
                tmp_file.unlink()
                if file_path.exists():
                    file_path.unlink()
                    default_logger.warning(
                        f'Нет данных для {file_path}. Файл удален.'
                    )

        except Exception as e:
            default_logger.exception(
                f'Ошибка при генерации CSV {file_path}: {e}'
            )
            if tmp_file.exists():
                tmp_file.unlink()
            raise

    @timer(default_logger)
    def update_actual_file(self):
        """
        Обновляет файл текущих инцидентов:
        - Все открытые
        - Все зарегестрированные с первого числа предыдущего месяца
        """
        fresh, _ = is_file_fresh(ACTUAL_INCIDENTS_FILE, ACTUAL_INCIDENTS_TTL)
        # if fresh:
        #     return

        first_day = get_first_day_prev_month()
        qs = self.qs.filter(
            Q(is_incident_finish=False) | Q(incident_date__gte=first_day)
        )

        self._generate_csv_file(qs, ACTUAL_INCIDENTS_FILE)

    @timer(default_logger)
    def update_archive_file(self, year: int, quarter: int):
        """
        Обновляет архивный файл за конкретный квартал.
        Файл сохраняется как: archive/YYYY/Q{quarter}.csv
        """
        if not ARCHIVE_INCIDENTS_DIR.exists():
            ARCHIVE_INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)

        file_name = f'archive_{year}_Q{quarter}_incidents.csv'
        file_path = ARCHIVE_INCIDENTS_DIR / file_name

        fresh, _ = is_file_fresh(file_path, ARCHIVE_INCIDENTS_TTL)
        if fresh:
            return

        tz = timezone.get_current_timezone()

        # Фильтрация по кварталам:
        if quarter == 1:
            start_date = timezone.make_aware(
                datetime(year, 1, 1, 0, 0, 0), tz
            )
            end_date = timezone.make_aware(
                datetime(year, 4, 1, 0, 0, 0), tz
            )
        elif quarter == 2:
            start_date = timezone.make_aware(
                datetime(year, 4, 1, 0, 0, 0), tz
            )
            end_date = timezone.make_aware(
                datetime(year, 7, 1, 0, 0, 0), tz
            )
        elif quarter == 3:
            start_date = timezone.make_aware(
                datetime(year, 7, 1, 0, 0, 0), tz
            )
            end_date = timezone.make_aware(
                datetime(year, 10, 1, 0, 0, 0), tz
            )
        else:
            start_date = timezone.make_aware(
                datetime(year, 10, 1, 0, 0, 0), tz
            )
            end_date = timezone.make_aware(
                datetime(year + 1, 1, 1, 0, 0, 0), tz
            )

        # Фильтрация по дате регистрации:
        qs = self.qs.filter(
            incident_date__gte=start_date,
            incident_date__lt=end_date
        )

        self._generate_csv_file(qs, file_path)
