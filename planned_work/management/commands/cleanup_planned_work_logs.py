from django.core.management.base import BaseCommand
from django.utils import timezone

from core.loggers import planned_work_logger
from planned_work.constants import (
    CLEANUP_OLD_PLR_CHANGE_LOG_TTL,
    PLR_CHANGE_LOG_BATCH_SIZE,
)
from planned_work.models import PlannedWorkChangeLog


class Command(BaseCommand):
    help = (
        'Удаление старых записей журнала изменений для закрытых плановых работ'
    )

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - CLEANUP_OLD_PLR_CHANGE_LOG_TTL

        queryset = PlannedWorkChangeLog.objects.filter(
            created_at__lte=cutoff_date,
            planned_work__end_date__lte=cutoff_date,
        )

        total_count = queryset.count()

        if total_count == 0:
            planned_work_logger.debug(
                'Очистка журналов событий плановых работ не требуется.'
            )
            return

        deleted_count = 0

        while True:
            pks = list(
                queryset.values_list('pk', flat=True)
                [:PLR_CHANGE_LOG_BATCH_SIZE]
            )

            if not pks:
                break

            count, _ = PlannedWorkChangeLog.objects.filter(pk__in=pks).delete()
            deleted_count += count

            if count < PLR_CHANGE_LOG_BATCH_SIZE:
                break

        planned_work_logger.info(
            f'Удалено {deleted_count} записей журнала изменений '
            'плановых работ.'
        )
