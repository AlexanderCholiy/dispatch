# incidents/services/rvr_email.py
from typing import Iterable, Optional

from incidents.models import (
    Incident,
    IncidentSubType,
    IncidentType,
    RegionRvrEmailAssignment,
)


def resolve_rvr_emails(incident: Incident) -> list[str]:
    """
    Возвращает список уникальных email-адресов (str) для отправки
    уведомления по РВР-инциденту.

    Порядок разрешения (самый специфичный уровень побеждает):
      0. incident.region_responsible_user (если активен) — приоритет
         над всеми остальными уровнями;
      1. region + incident_type + incident_subtype
      2. region + incident_type
      3. region (без типа)
      4. Region.rvr_email (дефолт региона)

    Пустое назначение (запись есть, но emails пуст) пропускается —
    поиск продолжается на уровне выше.

    Возвращает [] если ничего не найдено.
    """
    # Уровень 0: ответственный пользователь региона — переопределяет всё.
    responsible = incident.region_responsible_user
    if responsible and responsible.is_active:
        return _unique([responsible.email])

    region = incident.pole.region if incident.pole else None
    if not region:
        return []

    # Один запрос: тянем все назначения региона сразу,
    # сортировку по специфичности делаем на Python.
    assignments = (
        RegionRvrEmailAssignment.objects
        .filter(region=region)
        .prefetch_related('emails')
    )

    addresses = _resolve_from_assignments(
        assignments,
        incident_type=incident.incident_type,
        incident_subtype=incident.incident_subtype,
    )
    if addresses:
        return _unique(addresses)

    # Фолбэк: дефолт региона:
    if region.rvr_email_id:
        return _unique([region.rvr_email.email])

    return []


def _resolve_from_assignments(
    assignments: Iterable[RegionRvrEmailAssignment],
    incident_type: Optional[IncidentType],
    incident_subtype: Optional[IncidentSubType],
) -> list[str]:
    """
    Сортирует назначения по специфичности и возвращает email-адреса
    первого непустого уровня.
    """
    ordered = sorted(assignments, key=_specificity, reverse=True)

    for assignment in ordered:
        if not _matches(assignment, incident_type, incident_subtype):
            continue
        # .values_list тянет адреса одним запросом, без объектов.
        addresses = list(assignment.emails.values_list('email', flat=True))
        if addresses:
            return addresses
        # Пустое назначение — не считаем переопределением, идём выше.

    return []


def _specificity(assignment: RegionRvrEmailAssignment) -> int:
    """Чем больше заполненных FK, тем специфичнее назначение."""
    return (
        (1 if assignment.incident_type_id else 0)
        + (2 if assignment.incident_subtype_id else 0)
    )


def _matches(
    assignment: RegionRvrEmailAssignment,
    incident_type: Optional[IncidentType],
    incident_subtype: Optional[IncidentSubType],
) -> bool:
    """Проверяет, что назначение применимо к данному типу/подтипу."""
    if assignment.incident_type_id:
        if (
            not incident_type
            or assignment.incident_type_id != incident_type.pk
        ):
            return False

    if assignment.incident_subtype_id:
        if (
            not incident_subtype
            or assignment.incident_subtype_id != incident_subtype.pk
        ):
            return False

    return True


def _unique(addresses: Iterable[Optional[str]]) -> list[str]:
    """
    Убирает пустые адреса и дубликаты (регистронезависимо),
    сохраняя порядок первого появления.
    """
    seen: set[str] = set()
    result: list[str] = []
    for addr in addresses:
        if not addr:
            continue
        normalized = addr.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
