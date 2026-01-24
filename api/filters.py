from django.db.models import QuerySet
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
