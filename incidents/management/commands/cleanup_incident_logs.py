from django.core.management.base import BaseCommand
from django.utils import timezone

from core.loggers import incident_logger
from incidents.constants import (
    CLEANUP_OLD_INCIDENT_CHANGE_LOG_TTL,
    INCIDENT_CHANGE_LOG_BATCH_SIZE,
)
from incidents.models import (
    IncidentChangeLog,
    IncidentHistory,
)


class Command(BaseCommand):
    help = (
        'Удаление старых записей журнала изменений '
        'и истории писем для закрытых инцидентов.'
    )

    def handle(self, *args, **options):
        self.clean_incident_change_log()
        self.clean_incident_history()

    def clean_incident_change_log(self):
        cutoff_date = timezone.now() - CLEANUP_OLD_INCIDENT_CHANGE_LOG_TTL

        queryset = IncidentChangeLog.objects.filter(
            created_at__lte=cutoff_date,
            incident__is_incident_finish=True,
            incident__incident_finish_date__lte=cutoff_date,
        )

        total_count = queryset.count()

        if total_count == 0:
            incident_logger.debug(
                'Очистка журналов событий инцидентов не требуется.'
            )
            return

        deleted_count = 0

        while True:
            pks = list(
                queryset.values_list('pk', flat=True)
                [:INCIDENT_CHANGE_LOG_BATCH_SIZE]
            )

            if not pks:
                break

            count, _ = IncidentChangeLog.objects.filter(pk__in=pks).delete()
            deleted_count += count

            if count < INCIDENT_CHANGE_LOG_BATCH_SIZE:
                break

        incident_logger.info(
            f'Удалено {deleted_count} записей журнала изменений инцидентов.'
        )

    def clean_incident_history(self):
        cutoff_date = timezone.now() - CLEANUP_OLD_INCIDENT_CHANGE_LOG_TTL

        queryset = IncidentHistory.objects.filter(
            insert_date__lte=cutoff_date,
            incident__is_incident_finish=True,
            incident__incident_finish_date__lte=cutoff_date,
        )

        total_count = queryset.count()

        if total_count == 0:
            incident_logger.debug(
                'Очистка истории инцидентов не требуется.'
            )
            return

        deleted_count = 0

        while True:
            pks = list(
                queryset.values_list('pk', flat=True)
                [:INCIDENT_CHANGE_LOG_BATCH_SIZE]
            )

            if not pks:
                break

            count, _ = IncidentHistory.objects.filter(pk__in=pks).delete()
            deleted_count += count

            if count < INCIDENT_CHANGE_LOG_BATCH_SIZE:
                break

        incident_logger.info(
            f'Удалено {deleted_count} записей истории инцидентов.'
        )
