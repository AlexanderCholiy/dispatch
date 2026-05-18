from django.core.management.base import BaseCommand
from django.db.models import Q

from core.loggers import monitoring_logger
from core.wraps import timer
from monitoring.models import DeviceStatus, DeviceType, MSysModem


class Command(BaseCommand):
    help = 'Уведомление о включении РЩУ рядом с ближайшей опорой'

    @timer(monitoring_logger, False)
    def handle(self, *args, **kwargs):
        devices = self.get_new_devices()

        for device in devices:
            print(device)

    def get_new_devices(self):
        base_qs = (
            MSysModem.objects
            .filter(
                level__in=[DeviceType.RHU_NEW, DeviceType.HU_NEVA_NEW],
                status=DeviceStatus.MODEM_NORMAL,
            )
            .exclude(
                Q(modem_latitude__isnull=True)
                | Q(modem_longtitude__isnull=True)
            )
        )

        exclude_zones = Q()

        # Зона Allics:
        exclude_zones |= Q(
            modem_latitude__gt=55.8073, modem_latitude__lt=55.8085,
            modem_longtitude__gt=37.8335, modem_longtitude__lt=37.8346
        )

        # Зона Kvanta:
        exclude_zones |= Q(
            modem_latitude__gt=55.606, modem_latitude__lt=55.621,
            modem_longtitude__gt=37.572, modem_longtitude__lt=37.599
        )

        # Зона DC Telecom:
        exclude_zones |= Q(
            modem_latitude__gt=55.841, modem_latitude__lt=55.845,
            modem_longtitude__gt=37.530, modem_longtitude__lt=37.540
        )

        # Зона DI Group:
        exclude_zones |= Q(
            modem_latitude__gt=55.9608, modem_latitude__lt=55.975,
            modem_longtitude__gt=38.050, modem_longtitude__lt=38.071
        )

        # Зона NPK Energo-Sila (1):
        exclude_zones |= Q(
            modem_latitude__gt=55.3, modem_latitude__lt=55.6,
            modem_longtitude__gt=46.2, modem_longtitude__lt=47.0
        )

        # Зона NPK Energo-Sila (2):
        exclude_zones |= Q(
            modem_latitude__gt=55.8, modem_latitude__lt=56.6,
            modem_longtitude__gt=47.3, modem_longtitude__lt=47.9
        )

        # Зона ElektroConstrakshn:
        exclude_zones |= Q(
            modem_latitude__gt=56.0, modem_latitude__lt=56.2,
            modem_longtitude__gt=47.2, modem_longtitude__lt=47.3
        )

        # Зона TIK:
        exclude_zones |= Q(
            modem_latitude__gt=57.8, modem_latitude__lt=60.1,
            modem_longtitude__gt=56.1, modem_longtitude__lt=56.3
        )

        return base_qs.exclude(exclude_zones)
