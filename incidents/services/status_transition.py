from typing import Optional

from incidents.constants import STATUS_TRANSITIONS, DEFAULT_STATUS_NAME

from incidents.models import IncidentStatus

from django.db.models import Case, When


def get_allowed_statuses(
    current_status: Optional[IncidentStatus] = None
) -> list[IncidentStatus]:
    """
    Возвращает список статусов, в которые можно перейти из текущего статуса.
    """
    allowed_names = [current_status.name] if current_status else []

    if current_status is None:
        allowed_names.extend(STATUS_TRANSITIONS.get(DEFAULT_STATUS_NAME, []))
    else:
        allowed_names.extend(STATUS_TRANSITIONS.get(current_status.name, []))

    if not allowed_names:
        return IncidentStatus.objects.select_related('status_type').none()

    # Сохраняем порядок из списка allowed_names
    whens = [
        When(name=name, then=pos) for pos, name in enumerate(allowed_names)
    ]
    return (
        IncidentStatus.objects.select_related('status_type')
        .filter(name__in=allowed_names).order_by(Case(*whens))
    )
