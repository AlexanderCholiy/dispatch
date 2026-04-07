from django.core.management.base import BaseCommand
from django.db.models import F, Max, OuterRef, Subquery

from core.loggers import mqtt_logger
from core.wraps import timer
from mqtt.constants import CELL_INFO_TTL
from mqtt.models import CellInfo


class Command(BaseCommand):
    help = (
        'Очистка старых данных с сохранением последних N дней активности '
        'для каждого устройства'
    )

    @timer(mqtt_logger)
    def handle(self, *args, **options):
        try:
            latest_per_device = CellInfo.objects.values('device_id').annotate(
                max_event=Max('event_datetime')
            )

            if not latest_per_device.exists():
                mqtt_logger.debug('Нет данных для очистки.')
                return

            max_date_subquery = CellInfo.objects.filter(
                device_id=OuterRef('device_id')
            ).values('device_id').annotate(
                m=Max('event_datetime')
            ).values('m')

            qs_with_max = CellInfo.objects.annotate(
                device_last_seen=Subquery(max_date_subquery)
            )

            cutoff_threshold = F('device_last_seen') - CELL_INFO_TTL

            records_to_delete = qs_with_max.filter(
                event_datetime__lt=cutoff_threshold
            )

            count_to_delete = records_to_delete.count()

            if count_to_delete == 0:
                mqtt_logger.debug('Нет записей, подлежащих удалению.')
                return

            deleted_count, _ = records_to_delete.delete()

            if count_to_delete:
                mqtt_logger.info(
                    'Успешно удалено записей: '
                    f'{deleted_count} / {count_to_delete}'
                )

        except Exception as e:
            mqtt_logger.exception(f'Ошибка при очистке: {e}')
