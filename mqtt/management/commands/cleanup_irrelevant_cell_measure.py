from django.core.management.base import BaseCommand
from django.db.models import F, Max, Min, OuterRef, Subquery
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import mqtt_logger
from core.wraps import timer
from mqtt.constants import CELL_MEASSURE_TTL, MQTT_DEVICE_BATCH_SIZE
from mqtt.models import CellMeasure


class Command(BaseCommand):
    help = (
        'Очистка: оставляем последние N дней активности для каждого устройства'
    )

    @timer(mqtt_logger)
    def handle(self, *args, **options):
        try:
            devices_with_old_data = (
                CellMeasure.objects
                .values('device_id')
                .annotate(
                    max_dt=Max('event_datetime'),
                    min_dt=Min('event_datetime')
                )
                .filter(min_dt__lt=F('max_dt') - CELL_MEASSURE_TTL)
                .values_list('device_id', flat=True)
            )

            if not devices_with_old_data.exists():
                mqtt_logger.debug(
                    'Нет устройств со старой историей для очистки.'
                )
                return

            device_ids_to_clean = list(devices_with_old_data)
            if not device_ids_to_clean:
                return

            total_deleted = 0

            with tqdm(
                total=len(device_ids_to_clean),
                desc='Очистка CellMeasure',
                colour='cyan',
                position=0,
                leave=True,
                disable=not DEBUG_MODE,
            ) as pbar:
                for i in range(
                    0, len(device_ids_to_clean), MQTT_DEVICE_BATCH_SIZE
                ):
                    batch_ids = device_ids_to_clean[
                        i:i + MQTT_DEVICE_BATCH_SIZE
                    ]

                    latest_subquery = (
                        CellMeasure.objects
                        .filter(
                            device_id__in=batch_ids,
                            device_id=OuterRef('device_id'),
                        )
                        .values('device_id')
                        .annotate(max_dt=Max('event_datetime'))
                        .values('max_dt')
                    )

                    qs_to_delete = (
                        CellMeasure.objects
                        .filter(device_id__in=batch_ids)
                        .annotate(
                            last_device_activity=Subquery(latest_subquery)
                        )
                        .filter(
                            event_datetime__lt=(
                                F('last_device_activity') - CELL_MEASSURE_TTL
                            )
                        )
                    )

                    deleted_count, _ = qs_to_delete.delete()
                    total_deleted += deleted_count

                    pbar.update(i)

            ttl_str = (
                f'{CELL_MEASSURE_TTL.days} дн.'
                if CELL_MEASSURE_TTL.days > 0 else str(CELL_MEASSURE_TTL)
            )
            mqtt_logger.info(
                f'Очистка завершена. '
                f'Удалено {total_deleted:,} записей. '
                f'Сохранена история активности за последние {ttl_str} '
                'для каждого устройства.'
            )

        except Exception as e:
            mqtt_logger.exception(f'Ошибка при очистке данных: {e}')
