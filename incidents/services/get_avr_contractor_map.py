from django.core.cache import cache

from ts.constants import POLE_CACHE_TTL, UNDEFINED_CASE
from ts.models import AVRContractor

AVRContractorMap = dict[int, str]


def get_avr_contractor_map() -> AVRContractorMap:
    """
    Возвращает словарь: { id_подрядчика: "Название подрядчика" }
    Данные берутся из кеша или формируются из БД при первом запросе.
    """

    def fetch_data():
        data_list = list(
            AVRContractor.objects
            .exclude(contractor_name=UNDEFINED_CASE)
            .order_by('contractor_name')
            .values_list('id', 'contractor_name')
        )

        return {item[0]: item[1] for item in data_list}

    cache_key = 'incident_filter_avr_contractor_map'

    contractor_map = cache.get_or_set(
        cache_key,
        fetch_data,
        POLE_CACHE_TTL,
    )

    return contractor_map
