from django.core.cache import cache

from incidents.constants import MAX_INCIDENTS_INFO_CACHE_SEC
from incidents.models import RVRPriority

RVRPriorityMap = dict[int, dict]


def get_rvr_priority_map() -> RVRPriorityMap:
    """
    Данные берутся из кеша или формируются из БД при первом запросе.
    """
    def fetch_data():
        data_list = list(
            RVRPriority.objects.all()
            .order_by('name')
            .values_list('id', 'name', 'description')
        )
        return {
            item[0]: {
                'name': item[1],
                'description': item[2]
            }
            for item in data_list
        }

    cache_key = 'incident_filter_incident_rvr_priority_map'

    incident_rvr_priority_map = cache.get_or_set(
        cache_key,
        fetch_data,
        MAX_INCIDENTS_INFO_CACHE_SEC,
    )

    return incident_rvr_priority_map
