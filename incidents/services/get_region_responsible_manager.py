from django.core.cache import cache

from ts.constants import REGION_RESPONSIBLE_MANAGER_CACHE_TTL
from ts.models import Region

ResponsibleManagerMap = dict[str, list[int]]


def get_region_responsible_managers() -> ResponsibleManagerMap:
    """
    Возвращает словарь: { "Имя Менеджера": [id_региона1, id_региона2, ...] }
    Данные берутся из кеша или формируются из БД при первом запросе.
    """

    def fetch_data():
        values_list = list(
            Region.objects.filter(responsible_manager__isnull=False)
            .values_list('responsible_manager', 'id')
            .order_by('responsible_manager')
        )

        result_map: ResponsibleManagerMap = {}

        for manager_name, region_id in values_list:
            if manager_name not in result_map:
                result_map[manager_name] = []
            result_map[manager_name].append(region_id)

        return result_map

    responsible_manager_map = cache.get_or_set(
        'incident_filter_region_responsible_manager',
        fetch_data,
        REGION_RESPONSIBLE_MANAGER_CACHE_TTL,
    )

    return responsible_manager_map
