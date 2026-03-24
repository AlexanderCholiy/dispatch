from django.core.cache import cache

from ts.constants import OPERATORS_CACHE_TTL
from ts.models import BaseStationOperator


def get_operators_group() -> list[str]:
    cache.delete('operator_group_filter')

    result = cache.get_or_set(
        'operator_group_filter',
        lambda: list(
            BaseStationOperator.objects.filter(operator_group__isnull=False)
            .exclude(operator_group__regex=r'^\s*$')
            .order_by('operator_group')
            .values_list('operator_group', flat=True)
            .distinct()
        ),
        OPERATORS_CACHE_TTL,
    )

    return result
