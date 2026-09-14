import math
import os
from http import HTTPStatus
from typing import TypedDict

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Q, QuerySet, Subquery
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from core.constants import DEBUG_MODE
from core.loggers import monitoring_2_logger
from core.services.haversine_distance import haversine_distance
from core.wraps import timer
from monitoring.constants import (
    FACTORIES_ZONES,
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
from monitoring_2.constants import (
    HU_NEVA_NEW_ID,
    NORMAL_STATUS_ID,
    NOTIFICATION_FAILED_CACHE_KEY,
    NOTIFICATION_FAILED_CACHE_TIMEOUT,
    NOTIFICATION_POLE_UP_URL,
    POLE_UP_ACTION_KEY,
    RHU_NEW_ID,
)
from monitoring_2.models import Counter, Modem, Pole


class NearestDevice(TypedDict):
    pole: str
    distance: float
    address: str


class Command(BaseCommand):
    help = 'Уведомление о включении РЩУ рядом с ближайшей опорой'

    @timer(monitoring_2_logger)
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

            monitoring_2_logger.warning(
                'Задача отправки уведомлений о включении опор уже запущена. '
                'Пропуск.'
            )
            return

        try:
            self.notify_pole_rhu_up()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            monitoring_2_logger.exception(
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
            monitoring_2_logger.debug(
                'Устройств требующих отправки уведомлений не обнаружено'
            )
            return

        if total > MAX_NEW_RHU_NOTIFICATION:
            monitoring_2_logger.warning(
                f'Слишком много новых опор ({total} шт.). Пропуск задачи.'
            )
            return

        poles_list = list(
            Pole.objects
            .exclude(coordinates__isnull=True)
            .values('pole', 'address', 'coordinates')
        )

        if not poles_list:
            monitoring_2_logger.warning(
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
                ip = device.ip.strip()
                dev_lon = device.coordinates.x
                dev_lat = device.coordinates.y

                # Фильтрация по зонам (заводы где собирают щиты):
                is_excluded = False

                for factory_lat, factory_lon in FACTORIES_ZONES:
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
                    pole_longtitude = pole['coordinates'].x
                    pole_latitude = pole['coordinates'].y

                    dist = haversine_distance(
                        dev_lat,
                        dev_lon,
                        pole_latitude,
                        pole_longtitude,
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
                    monitoring_2_logger.debug(
                        'Расстояние между контроллером '
                        f'{ip} и ближайшей опорой '
                        'превышает максимальный лимит '
                        f'{MAX_MIN_LEN_BETWEEN_MODEM_AND_POLE} м. Пропуск.'
                    )
                    skipped_count += 1
                    pbar_outer.update(1)
                    continue

                nearest_pole = top_nearest_poles[0]

                dev_type_name = str(device.level).replace('NEW', '').strip()

                subject = (
                    f'Включение {dev_type_name} '
                    f'на опоре {nearest_pole["pole"]}'
                )

                msg_lines = []

                msg_lines.append(
                    f'На опоре {nearest_pole["pole"]} '
                    f'[{nearest_pole["address"]}] '
                    f'зафиксировано включение оборудования [{dev_type_name}].'
                )
                msg_lines.append('')
                msg_lines.append(
                    f'• IP адрес: {ip}'
                )

                serial = device.serial
                cabinet = device.cabinet
                counters: QuerySet[Counter] = device.counters.all()
                counters_numbers = (
                    sorted(c.counter_number.strip() for c in counters)
                    if counters else None
                )

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

                if counters_numbers:
                    msg_lines.append(
                        f'• Счётчики: {", ".join(counters_numbers)}'
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
                                f'[{pole_info["pole"]}] '
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

                self.mark_notification_sent(ip)
                self._remove_from_failed_cache(ip)

                try:
                    if not DEBUG_MODE:
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
                    monitoring_2_logger.exception(
                        f'Ошибка отправки письма для {ip}: {e}'
                    )
                    self._cache_failed_notification(ip)

                pbar_outer.update(1)

        success_count = total - skipped_count
        if success_count:
            monitoring_2_logger.info(
                f'Отправлено: {success_count} уведомлений о включении опор: '
                f'{", ".join(new_poles)}. '
                f'Всего обработано: {total}, Пропущено: {skipped_count}'
            )

    def mark_notification_sent(
        self,
        ip: str,
        timeout: int = 10,
        retries: int = 3,
        backoff: float = 1.0,
    ):
        """
        Проставляет флаг отправки уведомления в БД Мониторинга 2.0.

        PUT /api/integration/notifications/modem/<action>/sent?ip=<ip>

        :param ip: IP адрес модема
        :param timeout: таймаут запроса в секундах
        :param retries: количество повторных попыток
        :param backoff: множитель задержки между попытками (сек)
        """
        ip = ip.strip()
        session = requests.Session()
        retry = Retry(
            total=retries,
            backoff_factor=backoff,
            status_forcelist=[
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            ],
            allowed_methods=['PUT'],
        )
        session.mount('https://', HTTPAdapter(max_retries=retry))

        try:
            response = session.put(
                NOTIFICATION_POLE_UP_URL,
                params={'ip': ip},
                timeout=timeout,
            )
            response.raise_for_status()
            monitoring_2_logger.debug(
                f'Флаг "{POLE_UP_ACTION_KEY}" для {ip} проставлен успешно '
                f'(status={response.status_code})'
            )

        except requests.exceptions.RequestException as e:
            monitoring_2_logger.error(
                f'Ошибка простановки флага "{POLE_UP_ACTION_KEY}" '
                f'для {ip} после {retries} попыток: {e}'
            )
            raise

    def _cache_failed_notification(self, ip: str):
        """Кладёт IP в кеш для повторной отправки."""
        failed_ips: list[str] = cache.get(NOTIFICATION_FAILED_CACHE_KEY, [])
        if ip not in failed_ips:
            failed_ips.append(ip)
            cache.set(
                NOTIFICATION_FAILED_CACHE_KEY,
                failed_ips,
                timeout=NOTIFICATION_FAILED_CACHE_TIMEOUT,
            )
            monitoring_2_logger.warning(
                f'IP {ip} добавлен в очередь повторной отправки '
                f'(всего в очереди: {len(failed_ips)})'
            )

    def _remove_from_failed_cache(self, ip: str):
        """Удаляет IP из кеша после успешной отправки."""
        failed_ips: list[str] = cache.get(NOTIFICATION_FAILED_CACHE_KEY, [])
        if ip in failed_ips:
            failed_ips.remove(ip)
            if failed_ips:
                cache.set(
                    NOTIFICATION_FAILED_CACHE_KEY,
                    failed_ips,
                    timeout=NOTIFICATION_FAILED_CACHE_TIMEOUT,
                )
            else:
                cache.delete(NOTIFICATION_FAILED_CACHE_KEY)

    def get_new_devices(self):
        stuck_ips: list[str] = cache.get(NOTIFICATION_FAILED_CACHE_KEY, [])
        base_qs = (
            Modem.objects
            .filter(
                level__id__in=[RHU_NEW_ID, HU_NEVA_NEW_ID],
                status__id=NORMAL_STATUS_ID,
            )
            .exclude(
                Q(coordinates__isnull=True)
                | Q(modem_notifications__action=POLE_UP_ACTION_KEY)
            )
        )

        if stuck_ips:
            stuck_qs = Modem.objects.filter(ip__in=stuck_ips)
            union_qs = base_qs.union(stuck_qs)
            qs = Modem.objects.filter(
                id__in=Subquery(union_qs.values('id'))
            )
        else:
            qs = base_qs

        return (
            qs
            .select_related('level', 'status')
            .prefetch_related(
                'counters',
                'modem_pole_relations',
                'modem_notifications',
            )
            .order_by('last_data_at', 'id')
        )
