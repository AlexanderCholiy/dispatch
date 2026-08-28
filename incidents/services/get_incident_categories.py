from django.core.cache import cache

from incidents.constants import MAX_INCIDENTS_INFO_CACHE_SEC
from incidents.models import IncidentCategory


def get_incident_categories() -> list[dict]:
    """
    Данные берутся из кеша или формируются из БД при первом запросе.
    """
    cache_key = 'incident_filter_categories'

    categories = cache.get_or_set(
        cache_key,
        lambda: list(
            IncidentCategory.objects.all()
            .order_by('name')
            .values('id', 'name', 'description')
        ),
        MAX_INCIDENTS_INFO_CACHE_SEC,
    )

    return categories
