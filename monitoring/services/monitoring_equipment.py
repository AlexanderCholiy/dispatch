from django.db.models import Q
from itertools import islice
from django.core.cache import cache
from typing import TypedDict, Optional

from datetime import datetime, timedelta
from django.utils import timezone

from monitoring.constants import (
    MONITORING_EQUIPMENT_CACHE_TTL,
    CHUNKED_MONITORING_QS,
    MONITORING_EQUIPMENT_CACHE_KEY,
    UNDEFINED_POLE_CASE,
)

from core.loggers import monitoring_logger


from monitoring.models import MSysModem
from ts.models import Pole


class MonitoringEquipment(TypedDict):
    modem_ip: Optional[str]
    pole_1: Optional[str]
    pole_2: Optional[str]
    pole_3: Optional[str]
    level: int
    status: int
    updated_at: Optional[datetime]


def get_monitiring_cache_equipment(
    pole: str
) -> Optional[list[MonitoringEquipment]]:
    cached_data: dict[str, list[MonitoringEquipment]] = cache.get(
        MONITORING_EQUIPMENT_CACHE_KEY
    )

    if cached_data is not None:
        return cached_data.get(pole)

    poles = set(Pole.objects.values_list('pole', flat=True))

    equipment: dict[str, MonitoringEquipment] = {}

    try:
        qs = (
            MSysModem.objects
            .values(
                'modem_ip',
                'pole_1',
                'pole_2',
                'pole_3',
                'level',
                'status',
                'updated_at',
            )
            .exclude(pole_1=UNDEFINED_POLE_CASE)
        )
    except Exception as e:
        monitoring_logger.exception(e)

    now = timezone.now()

    for row in qs.iterator(chunk_size=CHUNKED_MONITORING_QS):
        updated_at = row['updated_at']

        if updated_at:
            moscow_tz = timezone.get_current_timezone()
            updated_at = updated_at.replace(tzinfo=moscow_tz)

            if timezone.is_naive(updated_at):
                updated_at = timezone.make_aware(updated_at, moscow_tz)

            future_limit = now + timedelta(minutes=15)
            past_limit = now - timedelta(days=365 * 10)

            if updated_at > future_limit or updated_at < past_limit:
                updated_at = None
        else:
            updated_at = None

        row_result: MonitoringEquipment = {
            'modem_ip': (row['modem_ip'] or '').strip() or None,
            'pole_1': (row['pole_1'] or '').strip() or None,
            'pole_2': (row['pole_2'] or '').strip() or None,
            'pole_3': (row['pole_3'] or '').strip() or None,
            'level': row['level'],
            'status': row['status'],
            'updated_at': updated_at,
        }

        for pole_field in ('pole_1', 'pole_2', 'pole_3'):
            pole_name = row_result[pole_field]
            if (
                pole_name
                and pole_name != UNDEFINED_POLE_CASE
                and pole_name in poles
            ):
                equipment.setdefault(pole_name, []).append(row_result)

    cache.set(
        MONITORING_EQUIPMENT_CACHE_KEY,
        equipment,
        timeout=MONITORING_EQUIPMENT_CACHE_TTL
    )

    return equipment.get(pole)
