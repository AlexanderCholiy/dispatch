from typing import TypedDict

from django.core.cache import cache
from django.db.models import Q

from incidents.models import Incident
from users.constants import USERS_CACHE_TTL
from users.models import Roles, User


class ResponsibleUsers(TypedDict):
    id: int
    full_name: str


def get_responsible_users() -> list[ResponsibleUsers]:
    responsible_users = cache.get_or_set(
        'incident_filter_responsible_users',
        lambda: [
            {
                'id': user.id,
                'full_name': user.get_full_name() or 'Новый пользователь'
            }
            for user in (
                User.objects.filter(
                    Q(role=Roles.DISPATCH, is_active=True)
                    | Q(id__in=Incident.objects.values_list(
                        'responsible_user_id', flat=True
                    ))
                )
                .distinct()
                .order_by('username')
            )
        ],
        USERS_CACHE_TTL,
    )

    return responsible_users
