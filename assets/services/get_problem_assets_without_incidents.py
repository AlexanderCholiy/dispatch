from typing import Optional

from django.core.cache import cache

from assets.constants import (
    CACHE_ASSETS_STATUS_TTL,
    CACHE_KEY_ASSETS_STATUS_PREFIX,
)
from assets.models import Equipment
from core.loggers import assets_logger
from incidents.models import Comment, Incident
from monitoring.constants import UNDEFINED_POLE_CASE
from monitoring.models import DeviceStatus, DeviceType, MSysModem
from ts.models import Pole
from users.models import User


def get_problem_assets_without_incidents(
    bot_user: Optional[User]
) -> dict[Pole, list[MSysModem]]:
    """
    Находит опоры с активным оборудованием, у которых есть проблемы
    и исключает те, по которым уже открыт инцидент.

    Также обновляет кэш статусов для каждого устройства и эскалирует
    инциденты с автозакрытием.

    Returns:
        Dict[Pole, List[MSysModem]]: Словарь {опора: список проблемных модемов}
    """

    active_equipment_qs = Equipment.objects.filter(is_active=True)

    if not active_equipment_qs.exists():
        return {}

    active_ips = list(
        active_equipment_qs.values_list('modem_ip', flat=True)
    )

    matching_monitoring_qs = MSysModem.objects.filter(
        modem_ip__in=active_ips,
        modem_mac__isnull=False,
        pole_1__isnull=False,
    ).select_related('pole_1')

    monitoring_lookup: dict[tuple[str, str], MSysModem] = {}
    for mon in matching_monitoring_qs:
        key = (mon.modem_ip.strip(), mon.modem_mac.upper().strip())
        monitoring_lookup[key] = mon

    active_err_assets: dict[Pole, list[MSysModem]] = {}

    for eq in active_equipment_qs:
        target_key = (eq.modem_ip.strip(), eq.modem_mac.upper().strip())
        cache_key = (
            f'{CACHE_KEY_ASSETS_STATUS_PREFIX}{target_key[0]}:{target_key[1]}'
        )

        if target_key not in monitoring_lookup:
            cache.set(
                cache_key,
                '⚠️ Нет в мониторинге',
                timeout=CACHE_ASSETS_STATUS_TTL
            )
            continue

        mon_obj = monitoring_lookup[target_key]

        devices_with_errors = (
            MSysModem.objects
            .filter(pole_1=mon_obj.pole_1)
            .exclude(status=DeviceStatus.MODEM_NORMAL)
        ).select_related('pole_1', 'status')

        has_problems_on_pole = devices_with_errors.exists()

        mon_pole_code: str = mon_obj.pole_1.pole.strip()

        if mon_pole_code == UNDEFINED_POLE_CASE:
            status_msg = (
                '❌ Привязка к опоре отсутствует'
                if has_problems_on_pole
                else 'ℹ️ ОК (привязка к опоре отсутствует)'
            )
            cache.set(cache_key, status_msg, timeout=CACHE_ASSETS_STATUS_TTL)
            continue

        try:
            pole = Pole.objects.get(pole=mon_pole_code)
        except Pole.DoesNotExist:
            status_msg = (
                '❌ Привязка к опоре TS отсутствует'
                if has_problems_on_pole
                else 'ℹ️ ОК (опора не найдена в TS)'
            )
            cache.set(cache_key, status_msg, timeout=CACHE_ASSETS_STATUS_TTL)
            continue

        current_status_id = mon_obj.status.id if mon_obj.status else None
        is_device_problematic = (
            current_status_id
            and current_status_id != DeviceStatus.MODEM_NORMAL
        )

        try:
            level_label = DeviceType(mon_obj.level).label
        except ValueError:
            level_label = f'щит №{mon_obj.level}'

        try:
            status_label = DeviceStatus(current_status_id).label
        except (ValueError, AttributeError):
            status_label = f'№{current_status_id}'

        if is_device_problematic:
            msg = (
                f'🔴 {level_label} [{status_label}] '
                f'на опоре {pole.pole}'
            )
        else:
            msg = (
                f'🟠 {level_label} [{status_label}], '
                f'но есть проблемы у других устройств (опора {pole.pole})'
            ) if has_problems_on_pole else (
                f'✅ {level_label} [{status_label}]'
            )

        if pole not in active_err_assets:
            active_err_assets[pole] = []
        active_err_assets[pole].append(mon_obj)

        cache.set(cache_key, msg, timeout=CACHE_ASSETS_STATUS_TTL)

    err_poles = list(active_err_assets.keys())

    if not err_poles:
        return {}

    err_poles_ids_with_incidents = set(
        Incident.objects
        .filter(pole__in=err_poles, is_incident_finish=False)
        .values_list('pole_id', flat=True)
    )

    comments_to_add = []
    incidents_to_bulk_update = []

    incidents_to_update = Incident.objects.filter(
        pole__in=err_poles,
        is_incident_finish=False,
        auto_close_date__isnull=False,
    ).select_related('pole')
    for incident in incidents_to_update:
        incident.auto_close_date = None
        incident.was_read = False
        incidents_to_bulk_update.append(incident)

        comment_text = (
            'Автозакрытие отменено: проблема с оборудованием сохраняется.'
        )

        if bot_user:
            comments_to_add.append({
                'incident': incident,
                'content': comment_text,
            })

    if incidents_to_bulk_update:
        Incident.objects.bulk_update(
            incidents_to_bulk_update,
            ['auto_close_date', 'was_read']
        )
        assets_logger.debug(
            f'Пакетно обновлено {len(incidents_to_bulk_update)} инцидентов '
            '(сброс даты автозакрытия и флаг не прочитано).'
        )

    if comments_to_add and bot_user:
        comment_objects = [
            Comment(
                incident=item['incident'],
                content=item['content'],
                author=bot_user,
            )
            for item in comments_to_add
        ]
        Comment.objects.bulk_create(comment_objects)

    final_active_err_assets = {
        pole: devices
        for pole, devices in active_err_assets.items()
        if pole.id not in err_poles_ids_with_incidents
    }

    return final_active_err_assets
