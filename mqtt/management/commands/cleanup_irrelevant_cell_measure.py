from django.core.management.base import BaseCommand
from django.db.models import F, Max, OuterRef, Subquery
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import mqtt_logger
from core.services.formatters import format_timedelta_readable
from core.wraps import timer
from mqtt.constants import CELL_MEASSURE_TTL, MQTT_DEVICE_BATCH_SIZE
from mqtt.models import CellMeasure


class Command(BaseCommand):
    help = 'Оставляем последнюю dt активности для каждой пары device, cell'

    @timer(mqtt_logger)
    def handle(self, *args, **options):
        try:
            unique_pairs = (
                CellMeasure.objects
                .values('device_id', 'cell_id')
                .distinct()
                .values_list('device_id', 'cell_id')
            )

            pairs_list = list(unique_pairs)

            if not pairs_list:
                mqtt_logger.debug('Нет данных для очистки.')
                return

            total_deleted = 0

            with tqdm(
                total=len(pairs_list),
                desc='Очистка CellMeasure (Device+Cell)',
                colour='cyan',
                position=0,
                leave=True,
                disable=not DEBUG_MODE,
            ) as pbar:
                for i in range(0, len(pairs_list), MQTT_DEVICE_BATCH_SIZE):
                    batch_pairs = pairs_list[i:i + MQTT_DEVICE_BATCH_SIZE]

                    max_dt_subquery = (
                        CellMeasure.objects
                        .filter(
                            device_id=OuterRef('device_id'),
                            cell_id=OuterRef('cell_id')
                        )
                        .values('device_id', 'cell_id')
                        .annotate(max_dt=Max('event_datetime'))
                        .values('max_dt')
                    )

                    qs_to_delete = (
                        CellMeasure.objects
                        .filter(
                            device_id__in=[p[0] for p in batch_pairs],
                            cell_id__in=[p[1] for p in batch_pairs],
                        )
                        .annotate(
                            group_max_dt=Subquery(max_dt_subquery)
                        )
                        .filter(
                            event_datetime__lt=F('group_max_dt')
                            - CELL_MEASSURE_TTL
                        )
                    )

                    deleted_count, _ = qs_to_delete.delete()
                    total_deleted += deleted_count
                    pbar.update(len(batch_pairs))

            ttl_str = format_timedelta_readable(CELL_MEASSURE_TTL)

            if total_deleted:
                mqtt_logger.info(
                    f'Очистка завершена. '
                    f'Удалено {total_deleted:,} записей. '
                    f'Сохранена история активности за последние {ttl_str} '
                    'для каждой комбинации (устройство, сота).'
                )

        except KeyboardInterrupt:
            mqtt_logger.warning('Процесс прерван.')
            raise

        except Exception as e:
            mqtt_logger.exception(f'Ошибка при очистке данных: {e}')
            raise
