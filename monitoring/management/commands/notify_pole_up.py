import math
import os
from typing import TypedDict

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.models import Q
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import monitoring_logger
from core.services.haversine_distance import haversine_distance
from core.wraps import timer
from monitoring.constants import (
    COORDINATE_PATTERN,
    FACTORY_EXCLUSION_RADIUS,
    GPS_NUMBER_DECIMAL_PLACES,
    MAX_MIN_LEN_BETWEEN_MODEM_AND_POLE,
    MAX_NEW_RHU_NOTIFICATION,
    MONITORING_CHUNK_SIZE,
    NOTIFY_NEW_POLE_EMAILS,
    NOTIFY_NEW_POLE_LOCK_KEY,
    NOTIFY_NEW_POLE_LOCK_TIMEOUT,
    TOP_N_NEAREST_POLES,
    TRETHHOLD_RATIO_BETWEEN_MODEM_AND_POLE,
)
from monitoring.models import DeviceStatus, DeviceType, MSysModem
from ts.models import Pole


class NearestDevice(TypedDict):
    pole: str
    distance: float
    address: str


class Command(BaseCommand):
    help = 'Уведомление о включении РЩУ рядом с ближайшей опорой'

    @timer(monitoring_logger)
    def handle(self, *args, **kwargs):
        acquired = cache.add(
            NOTIFY_NEW_POLE_LOCK_KEY, str(os.getpid()),
            timeout=NOTIFY_NEW_POLE_LOCK_TIMEOUT
        )

        if not acquired:
            ttl = cache.ttl(NOTIFY_NEW_POLE_LOCK_KEY)

            if ttl is None:
                acquired = cache.add(
                    NOTIFY_NEW_POLE_LOCK_KEY,
                    str(os.getpid()),
                    timeout=NOTIFY_NEW_POLE_LOCK_TIMEOUT
                )

            monitoring_logger.warning(
                'Задача отправки уведомлений о включении опор уже запущена. '
                'Пропуск.'
            )
            return

        try:
            self.notify_pole_rhu_up()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            monitoring_logger.exception(
                f'Ошибка отправки уведомлений о включении опор: {e}'
            )
        finally:
            cache.delete(NOTIFY_NEW_POLE_LOCK_KEY)

    def notify_pole_rhu_up(self):
        devices = self.get_new_devices()

        total = devices.count()
        skipped_count = 0
        new_poles: list[str] = []

        if not total:
            monitoring_logger.debug(
                'Устройств требующих отправки уведомлений не обнаружено'
            )
            return

        if total > MAX_NEW_RHU_NOTIFICATION:
            monitoring_logger.warning(
                f'Слишком много новых опор ({total} шт.). Пропуск задачи.'
            )
            return

        poles_list = list(
            Pole.objects.filter(
                pole_latitude__isnull=False,
                pole_longtitude__isnull=False,
            ).values(
                'pole', 'address', 'pole_latitude', 'pole_longtitude'
            )
        )

        if not poles_list:
            monitoring_logger.warning(
                'Опоры для поиска отсутствуют. Пропуск задачи.'
            )
            return

        with tqdm(
            total=total,
            desc='Подготовка уведомлений о включении опор',
            colour='cyan',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar_outer:
            for device in devices.iterator(chunk_size=MONITORING_CHUNK_SIZE):
                try:
                    ip = device.modem_ip.strip()
                    dev_lat_str = str(device.modem_latitude).strip()
                    dev_lon_str = str(device.modem_longtitude).strip()

                    if (
                        not COORDINATE_PATTERN.match(dev_lat_str)
                        or not COORDINATE_PATTERN.match(dev_lon_str)
                    ):
                        monitoring_logger.warning(
                            'Некорректный формат координат у '
                            f'{device.modem_ip.strip()}: '
                            f'lat="{dev_lat_str}", '
                            f'lon="{dev_lon_str}". Пропуск.'
                        )
                        skipped_count += 1
                        pbar_outer.update(1)
                        continue

                    dev_lat = float(dev_lat_str)
                    dev_lon = float(dev_lon_str)

                except ValueError:
                    monitoring_logger.error(
                        'Ошибка парсинга координат у '
                        f'{device.modem_ip.strip()}. Пропуск.'
                    )
                    skipped_count += 1
                    pbar_outer.update(1)
                    continue

                # Фильтрация по зонам (заводы где собирают щиты):
                zones = [
                    # Allics:
                    (55.810244, 37.833093),
                    # Kvanta:
                    (55.61364891050723, 37.585634328688705),
                    # DC Telecom:
                    (55.843576, 37.537767),
                    # DI Group:
                    (55.966669167, 38.06768783),
                    # NPK Energo-Sila:
                    (55.490010833, 46.424347),
                    (56.0100305, 47.594736),
                    # ElektroConstrakshn:
                    (56.10033, 47.258308667),
                    # TIK:
                    (57.9556695, 56.231073333),
                ]

                is_excluded = False

                for factory_lat, factory_lon in zones:
                    dist_to_center = haversine_distance(
                        dev_lat, dev_lon, factory_lat, factory_lon
                    )

                    if (
                        not isinstance(dist_to_center, (int, float))
                        or math.isnan(dist_to_center)
                        or math.isinf(dist_to_center)
                        or dist_to_center < FACTORY_EXCLUSION_RADIUS
                    ):
                        is_excluded = True
                        break

                if is_excluded:
                    pbar_outer.update(1)
                    skipped_count += 1
                    continue

                distances: list[NearestDevice] = []

                for pole in poles_list:
                    pole_latitude: float = pole['pole_latitude']
                    pole_longtitude: float = pole['pole_longtitude']

                    dist = haversine_distance(
                        dev_lat,
                        dev_lon,
                        pole['pole_latitude'],
                        pole['pole_longtitude'],
                    )

                    if (
                        not isinstance(dist, (int, float))
                        or math.isnan(dist)
                        or math.isinf(dist)
                        or dist > MAX_MIN_LEN_BETWEEN_MODEM_AND_POLE
                    ):
                        continue

                    gps = (
                        'широта: '
                        f'{round(pole_latitude, GPS_NUMBER_DECIMAL_PLACES)}, '
                        'долгота: '
                        f'{round(pole_longtitude, GPS_NUMBER_DECIMAL_PLACES)}'
                    )

                    distances.append({
                        'pole': pole['pole'],
                        'distance': dist,
                        'address': pole['address'] or gps,
                    })

                distances.sort(key=lambda x: x['distance'])

                top_nearest_poles: list[NearestDevice] = (
                    distances[:TOP_N_NEAREST_POLES]
                )

                if not top_nearest_poles:
                    monitoring_logger.debug(
                        'Расстояние между контроллером '
                        f'{device.modem_ip.strip()} и ближайшей опорой '
                        'превышает максимальный лимит '
                        f'{MAX_MIN_LEN_BETWEEN_MODEM_AND_POLE} м. Пропуск.'
                    )
                    skipped_count += 1
                    pbar_outer.update(1)
                    continue

                nearest_pole = top_nearest_poles[0]

                dev_type_name = (
                    'ЩУ-Нева'
                    if device.level == DeviceType.HU_NEVA_NEW else 'РЩУ'
                )

                subject = (
                    f'Включение {dev_type_name} '
                    f'на опоре {nearest_pole["pole"]}'
                )

                msg_lines = []

                msg_lines.append(
                    f'На опоре {nearest_pole["pole"]} '
                    f'({nearest_pole["address"]}) '
                    f'зафиксировано включение оборудования ({dev_type_name}).'
                )
                msg_lines.append('')
                msg_lines.append(
                    f'• IP адрес: {ip.strip()}'
                )

                serial = device.modem_serial
                cabinet = device.cabinet

                if serial:
                    msg_lines.append(
                        f'• Номер контроллера: {serial.strip()}'
                    )

                if cabinet:
                    msg_lines.append(f'• Номер шкафа: {cabinet.strip()}')

                    if cabinet.upper() == 'RVR':
                        msg_lines.append('')
                        msg_lines.append(
                            '*Контроллер выдавался для ремонта/замены '
                            'оборудования мониторинга.'
                        )

                dist_main = round(nearest_pole['distance'])
                msg_lines.append(
                    '• Расстояние между координатами контроллера и опорой: '
                    f'{dist_main} м.'
                )

                if (
                    dist_main < MAX_MIN_LEN_BETWEEN_MODEM_AND_POLE
                    and len(top_nearest_poles) > 1
                ):
                    for _, pole_info in enumerate(
                        top_nearest_poles[1:], start=2
                    ):
                        if pole_info is None:
                            continue

                        dist_other = round(pole_info['distance'])

                        if dist_other <= (
                            dist_main * TRETHHOLD_RATIO_BETWEEN_MODEM_AND_POLE
                        ):
                            msg_lines.append(
                                '• Ближайшая альтернативная опора '
                                f'({pole_info["pole"]}) '
                                f'находится в {dist_other} м.'
                            )
                        else:
                            break

                msg_lines.append('')
                msg_lines.append('---')

                msg_lines.append(
                    'Это автоматическое уведомление, '
                    'сгенерированное системой мониторинга.\n'
                    'Пожалуйста, не отвечайте на это письмо.'
                )

                full_message = '\n'.join(msg_lines)

                # Стоит запрет на редактирование данных мониторинга, поэтому
                # используем сырые SQL запросы:
                try:
                    if not DEBUG_MODE:
                        with connections['monitoring'].cursor() as cursor:
                            sql_update = """
                                UPDATE MSys_Modems
                                SET is_notification_sent = 1
                                WHERE ModemID = %s;
                            """
                            cursor.execute(sql_update, [device.modem_ip])

                        send_mail(
                            subject=subject,
                            message=full_message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=NOTIFY_NEW_POLE_EMAILS,
                            fail_silently=False,
                        )

                    new_poles.append(nearest_pole['pole'])

                except Exception as e:
                    skipped_count += 1
                    monitoring_logger.exception(
                        'Ошибка отправки письма для '
                        f'{device.modem_ip.strip()}: {e}'
                    )
                    with connections['monitoring'].cursor() as cursor:
                        sql_update = """
                            UPDATE MSys_Modems
                            SET is_notification_sent = 0
                            WHERE ModemID = %s;
                        """
                        cursor.execute(sql_update, [device.modem_ip])

                pbar_outer.update(1)

        success_count = total - skipped_count
        if success_count:
            monitoring_logger.info(
                f'Отправлено: {success_count} уведомлений о включении опор: '
                f'{", ".join(new_poles)}. '
                f'Всего обработано: {total}, Пропущено: {skipped_count}'
            )

    def get_new_devices(self):
        bad_gps = [
            'NULL',
            'nu.0',
            'K.0',
            'mp.945',
            '7.367e-06',
            '5.75e-06',
        ]

        return (
            MSysModem.objects
            .filter(
                level__in=[DeviceType.RHU_NEW, DeviceType.HU_NEVA_NEW],
                status=DeviceStatus.MODEM_NORMAL,
            )
            .exclude(
                Q(is_notification_sent=True)
                | Q(modem_latitude__isnull=True)
                | Q(modem_longtitude__isnull=True)
                | Q(modem_longtitude__in=bad_gps)
                | Q(modem_latitude__in=bad_gps)
            )
            .order_by('updated_at', 'modem_ip')
        )
