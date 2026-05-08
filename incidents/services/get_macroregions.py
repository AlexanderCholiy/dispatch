from django.core.cache import cache

from ts.constants import POLE_CACHE_TTL
from ts.models import MacroRegion

MacroRegionMap = dict[int, str]


def get_macro_region_map() -> MacroRegionMap:
    """
    Возвращает словарь: { id_макрорегиона: "Имя Макрорегиона" }
    Данные берутся из кеша или формируются из БД при первом запросе.
    """

    def fetch_data():
        data_list = list(
            MacroRegion.objects.all()
            .order_by('name')
            .values_list('id', 'name')
        )

        return {item[0]: item[1] for item in data_list}

    cache_key = 'incident_filter_macro_region_map'

    macro_region_map = cache.get_or_set(
        cache_key,
        fetch_data,
        POLE_CACHE_TTL,
    )

    return macro_region_map
