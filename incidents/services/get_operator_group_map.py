from django.core.cache import cache

from ts.constants import BASE_STATION_CACHE_TTL
from ts.models import BaseStationOperator

OperatorGroupMap = dict[str, list[int]]


def get_operator_group_map() -> OperatorGroupMap:
    """
    Возвращает словарь: { "Название Группы": [id_1, id_2, ...] }
    Собирает все ID записей BaseStationOperator для каждой уникальной группы.
    """

    def fetch_data():
        data_list = list(
            BaseStationOperator.objects
            .exclude(operator_group__isnull=True)
            .exclude(operator_group='')
            .order_by('operator_group', 'id')
            .values_list('operator_group', 'id')
        )

        result_map: OperatorGroupMap = {}

        for group_name, bs_id in data_list:
            if group_name not in result_map:
                result_map[group_name] = []
            result_map[group_name].append(bs_id)

        return result_map

    cache_key = 'incident_filter_operator_group_ids_map'

    group_map = cache.get_or_set(
        cache_key,
        fetch_data,
        BASE_STATION_CACHE_TTL,
    )

    return group_map
