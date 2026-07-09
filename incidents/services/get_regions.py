from django.core.cache import cache

from ts.constants import POLE_CACHE_TTL
from ts.models import Region

RegionMap = dict[int, str]


def get_region_map() -> RegionMap:
    """
    Возвращает словарь: { id_региона: "Имя региона" }
    Данные берутся из кеша или формируются из БД при первом запросе.
    """

    def fetch_data():
        data_list = list(
            Region.objects.all()
            .order_by('region_ru', 'region_en')
            .values_list('id', 'region_ru', 'region_en')
        )

        return {item[0]: item[1] or item[2] for item in data_list}

    cache_key = 'incident_filter_region_map'

    region_map = cache.get_or_set(
        cache_key,
        fetch_data,
        POLE_CACHE_TTL,
    )

    return region_map
