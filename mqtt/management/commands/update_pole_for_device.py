from django.core.management.base import BaseCommand
from django.db.models import Max
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import mqtt_logger
from core.wraps import timer
from monitoring.models import MSysModem
from mqtt.constants import MQTT_DB_BATCH_SIZE
from mqtt.models import Device
from ts.constants import UNDEFINED_CASE
from ts.models import Pole


class Command(BaseCommand):
    help = 'Обновление связи опора - устройство из данных мониторинга'

    _devices_to_update: list[Device] = []
    _updated_devices = 0

    @timer(mqtt_logger)
    def handle(self, *args, **options):
        monitoring_data = self._get_monitoring_data()
        ts_data = self._get_ts_data()

        total_devices = Device.objects.all()
        total_devices_cnt = total_devices.count()

        with tqdm(
            total=total_devices_cnt,
            desc='Обновление Device',
            colour='blue',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for device in Device.objects.all():
                mac_address = device.mac_address.upper().strip()
                modem_pole_number = monitoring_data.get(mac_address)
                pole = ts_data.get(modem_pole_number)

                if not modem_pole_number or not pole:
                    pbar.update(1)
                    continue

                if device.pole != pole:
                    device.pole = pole
                    self._devices_to_update.append(device)

                self._devices_butch_update()

                pbar.update(1)

            # Обновляем хвосты:
            self._devices_butch_update(update_anyway=True)

            if self._updated_devices:
                mqtt_logger.info(
                    f'Обработано: {total_devices_cnt}. '
                    f'Обновлено: Devices={self._updated_devices}.'
                )

    def _get_monitoring_data(self) -> dict[str, str]:
        qs = (
            MSysModem.objects
            .filter(
                pole_1__isnull=False,
                modem_mac__isnull=False,
            )
            .exclude(
                pole_1__pole=UNDEFINED_CASE
            )
            .values('modem_mac')
            .annotate(pole_number=Max('pole_1__pole'))
        )

        return {
            item['modem_mac'].upper().strip(): item['pole_number'].strip()
            for item in qs
        }

    def _get_ts_data(self) -> dict[str, Pole]:
        return {ob.pole: ob for ob in Pole.objects.all()}

    def _devices_butch_update(self, update_anyway: bool = False):
        if not self._devices_to_update:
            return

        if len(self._devices_to_update) >= MQTT_DB_BATCH_SIZE or update_anyway:
            Device.objects.bulk_update(
                self._devices_to_update,
                fields=['pole'],
            )

            self._updated_devices += len(self._devices_to_update)
            self._devices_to_update.clear()
