from typing import TypedDict

from django.core.cache import cache
from django.db.models import Q

from planned_work.models import PlannedWork
from users.constants import USERS_CACHE_TTL
from users.models import Roles, User


class PlannedWorkAuthor(TypedDict):
    id: int
    full_name: str


def get_planned_work_author() -> list[PlannedWorkAuthor]:
    authors = cache.get_or_set(
        'planned_work_filter_author',
        lambda: [
            {
                'id': user.id,
                'full_name': user.get_full_name() or 'Новый пользователь'
            }
            for user in (
                User.objects.filter(
                    Q(role=Roles.DISPATCH, is_active=True)
                    | Q(id__in=PlannedWork.objects.values_list(
                        'author_id', flat=True
                    ))
                )
                .distinct()
                .order_by('username')
            )
        ],
        USERS_CACHE_TTL,
    )

    return authors
