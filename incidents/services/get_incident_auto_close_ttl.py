from datetime import timedelta

from django.db.models import QuerySet

from incidents.constants import (
    AUTO_CLOSE_BY_OPERATOR_TTL,
    AUTO_CLOSE_DEFAULT_TTL,
)
from incidents.models import Incident
from ts.models import BaseStationOperator


def get_incident_auto_close_ttl(incident: Incident) -> timedelta:
    """
    Возвращает TTL для автоматического закрытия инцидента на основе
    группы операторов и максимально возможного TTL.
    """
    base_station = incident.base_station

    if not base_station:
        return AUTO_CLOSE_DEFAULT_TTL

    operators: QuerySet[BaseStationOperator] = base_station.operator.all()

    possible_ttls: list[timedelta] = []

    for operator_obj in operators:
        operator_group: str | None = operator_obj.operator_group

        key = None if not operator_group else operator_group.lower().strip()

        if not key:
            continue

        ttl = AUTO_CLOSE_BY_OPERATOR_TTL.get(key)

        if ttl:
            possible_ttls.append(ttl)

    if not possible_ttls:
        return AUTO_CLOSE_DEFAULT_TTL

    return max(possible_ttls)
