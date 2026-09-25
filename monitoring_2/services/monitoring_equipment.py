from datetime import datetime
from typing import Optional, TypedDict

from django.core.cache import cache
from django.db.models import QuerySet

from core.loggers import monitoring_2_logger
from core.wraps import func_timeout
from monitoring_2.constants import (
    MAX_EQUIPMENT_PER_POLE,
    MONITORING_2_EQUIPMENT_CACHE_KEY_PREFIX,
    MONITORING_2_EQUIPMENT_CACHE_TTL,
    UNDEFINED_POLE_CASE,
)
from monitoring_2.models import Modem, ModemLevel, ModemStatus


class MonitoringEquipment(TypedDict):
    ip: str
    serial: str
    level: str
    cabinet: Optional[str]
    status: str
    status_id: int
    last_data_at: Optional[datetime]
    slate: str


@func_timeout()
def monitoring_2_qs(pole: str) -> QuerySet[Modem] | None:
    modems_list = (
        Modem.objects
        .filter(modem_pole_relations__pole__pole=pole)
        .select_related('level', 'status')
    )[:MAX_EQUIPMENT_PER_POLE]

    if len(modems_list) > MAX_EQUIPMENT_PER_POLE - 1:
        monitoring_2_logger.warning(
            f'Опора "{pole}" имеет не менее {MAX_EQUIPMENT_PER_POLE} модемов.'
        )

    return modems_list


def monitoring_equipment_cache_key(pole: str) -> str:
    return f'{MONITORING_2_EQUIPMENT_CACHE_KEY_PREFIX}__{pole}'


def get_monitiring_2_cache_equipment(
    pole: str
) -> Optional[list[MonitoringEquipment]]:
    if pole == UNDEFINED_POLE_CASE:
        return

    cache_key = monitoring_equipment_cache_key(pole)
    cached_data: list[MonitoringEquipment] = cache.get(
        cache_key
    )

    if cached_data is not None:
        return cached_data

    equipments = []

    try:
        all_modems: QuerySet[Modem] = monitoring_2_qs(pole)

        for modem in all_modems:
            level: ModemLevel = modem.level
            level_str = level.description or f'ID: {level.id}'

            status: ModemStatus = modem.status
            status_str = (
                status.level_description or status.level or f'ID: {status.id}'
            )

            slate = modem.get_slate_display()

            row_result: MonitoringEquipment = {
                'ip': modem.ip,
                'serial': modem.serial,
                'level': level_str,
                'cabinet': modem.cabinet,
                'status': status_str,
                'status_id': status.id,
                'last_data_at': modem.last_data_at,
                'slate': slate,
            }

            equipments.append(row_result)

    except Exception as e:
        cache.set(cache_key, [], timeout=MONITORING_2_EQUIPMENT_CACHE_TTL)
        monitoring_2_logger.warning(f'Ошибка базы данных "monitoring_2": {e}')
        return None

    cache.set(cache_key, equipments, timeout=MONITORING_2_EQUIPMENT_CACHE_TTL)

    return equipments
