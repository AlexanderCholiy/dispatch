from datetime import date
from typing import Optional

from django.db.models import Q, QuerySet
from django_filters import (
    BooleanFilter,
    DateFromToRangeFilter,
    FilterSet,
)

from incidents.models import Incident

from .utils import get_first_day_prev_month


class IncidentReportFilter(FilterSet):
    incident_date = DateFromToRangeFilter()
    last_month = BooleanFilter(
        method='filter_last_month',
        label='Последний месяц',
        help_text=(
            'Возвращает инциденты с первого числа предыдущего месяца по '
            'сегодняшний день'
        )
    )

    class Meta:
        model = Incident
        fields = ('incident_date', 'last_month')

    def filter_last_month(
        self, queryset: QuerySet[Incident], name: str, value: bool
    ):
        """В Заявки с первого числа предыдущего месяца по сегодня"""
        if value:
            first_day_prev_month = get_first_day_prev_month()
            return queryset.filter(incident_date__gte=first_day_prev_month)
        return queryset


def get_incident_date_filter(start: Optional[date], end: Optional[date]) -> Q:
    q = Q()

    if start:
        q &= Q(incident_date__date__gte=start)
    if end:
        q &= Q(incident_date__date__lte=end)

    return q


def apply_responsible_user_filter(
    queryset: QuerySet[Incident],
    responsible_user_id: Optional[int | str],
) -> QuerySet[Incident]:
    if not responsible_user_id:
        return queryset

    if responsible_user_id == 'none':
        return queryset.filter(responsible_user_id__isnull=True)

    return queryset.filter(responsible_user_id=responsible_user_id)


def apply_bs_operator_group_filter(
    queryset: QuerySet[Incident],
    operator_group: Optional[str],
) -> QuerySet[Incident]:
    if not operator_group:
        return queryset

    if operator_group == 'none':
        return queryset.filter(
            base_station__operator__operator_group__isnull=True
        ).distinct()

    return queryset.filter(
        base_station__operator__operator_group=operator_group
    ).distinct()
