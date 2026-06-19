from django.core.cache import cache

from incidents.constants import MAX_INCIDENTS_INFO_CACHE_SEC
from incidents.models import IncidentSubType

IncidentSubTypeMap = dict[int, str]


def get_incident_subtype_map() -> IncidentSubTypeMap:
    """
    Возвращает словарь: { id_подтипа_инцидента: "Название подтипа" }
    Данные берутся из кеша или формируются из БД при первом запросе.
    """

    def fetch_data():
        data_list = list(
            IncidentSubType.objects.all()
            .order_by('name')
            .values_list('id', 'name')
        )

        return {item[0]: item[1] for item in data_list}

    cache_key = 'incident_filter_incident_subtype_map'

    incident_subtype_map = cache.get_or_set(
        cache_key,
        fetch_data,
        MAX_INCIDENTS_INFO_CACHE_SEC,
    )

    return incident_subtype_map
