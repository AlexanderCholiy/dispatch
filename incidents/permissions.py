from incidents.models import Incident
from users.models import User, Roles


def can_manage_incident(user: User, incident: Incident) -> bool:
    if not user.is_authenticated:
        return False
    return (
        user.role in [Roles.DISPATCH]
        or user.is_superuser
        or user.is_staff
        or (
            user.role == Roles.INTERN
            and incident.responsible_user_id == user.pk
        )
    )
