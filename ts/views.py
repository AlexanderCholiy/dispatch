import bisect
from sortedcontainers import SortedList

from dal import autocomplete
from .models import Pole, BaseStation
from django.core.cache import cache


from .constants import (
    POLES_PER_PAGE,
    BASE_STATIONS_PER_PAGE,
    POLE_CACHE_TTL,
    BASE_STATION_CACHE_TTL,
)
from users.models import Roles, User


def get_cached_poles() -> list[tuple[int, str]]:
    poles = cache.get('autocomplete_all_poles')
    if poles is None:
        poles = list(Pole.objects.only('id', 'pole').order_by('pole', 'id'))
        cache.set('autocomplete_all_poles', poles, POLE_CACHE_TTL)

    return poles


def get_cached_base_stations_all():
    """Кэш для быстрого поиска, если НЕ указан шифр опоры"""
    bs_list = cache.get('autocomplete_all_base_stations')
    if bs_list is None:
        bs_list = list(
            BaseStation.objects
            .select_related('pole')
            .exclude(bs_name__exact='')
            .only('id', 'bs_name', 'pole_id', 'pole__pole')
            .order_by('bs_name', 'pole_id', 'id')
        )
        cache.set(
            'autocomplete_all_base_stations', bs_list, BASE_STATION_CACHE_TTL
        )
    return bs_list


def get_cached_base_stations_by_pole():
    """Кэш для быстрого поиска, если указан шифр опоры"""
    bs_dict = cache.get('autocomplete_all_base_stations_by_pole')
    if bs_dict is None:
        bs_list = (
            BaseStation.objects
            .select_related('pole')
            .exclude(bs_name__exact='')
            .only('id', 'bs_name', 'pole__id', 'pole__pole')
            .order_by('bs_name', 'id')
        )
        bs_dict = {}
        for bs in bs_list:
            bs_dict.setdefault(bs.pole_id, []).append(bs)
        cache.set(
            'autocomplete_all_base_stations_by_pole',
            bs_dict,
            BASE_STATION_CACHE_TTL
        )
    return bs_dict


class PoleAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        user: User = self.request.user
        if (
            not user.is_authenticated
            or (user.role in [Roles.GUEST] and not user.is_superuser)
            or not user.is_active
        ):
            return Pole.objects.none()

        qs = get_cached_poles()
        q = (self.q or '').lower().strip()

        if q:
            i = bisect.bisect_left(qs, q, key=lambda p: p.pole.lower())
            results = []
            while i < len(qs) and qs[i].pole.lower().startswith(q):
                results.append(qs[i])
                if len(results) >= POLES_PER_PAGE:
                    break
                i += 1
            return results

        return list(qs[:POLES_PER_PAGE])


class BaseStationAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        user: User = self.request.user
        if (
            not user.is_authenticated
            or (user.role in [Roles.GUEST] and not user.is_superuser)
            or not user.is_active
        ):
            return BaseStation.objects.none()

        q = (self.q or '').lower().strip()
        pole_id = self.forwarded.get('pole')

        if pole_id:
            bs_dict = get_cached_base_stations_by_pole()
            candidates = bs_dict.get(int(pole_id), [])
        else:
            candidates = get_cached_base_stations_all()

        if q:
            i = bisect.bisect_left(
                candidates, q, key=lambda bs: bs.bs_name.lower()
            )
            results = []
            while (
                i < len(candidates)
                and candidates[i].bs_name.lower().startswith(q)
            ):
                results.append(candidates[i])
                if len(results) >= BASE_STATIONS_PER_PAGE:
                    break
                i += 1
            return results

        return candidates[:BASE_STATIONS_PER_PAGE]

    def get_result_label(self, item):
        """Формируем label для Select2: bs_name + шифр опоры"""
        bs_name = item.bs_name or 'unknown'
        pole_code = getattr(getattr(item, 'pole', None), 'pole', 'unknown')
        return f'{bs_name} [{pole_code}]'
