from datetime import date, timedelta
from typing import Optional

from django.db.models import (
    Case,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    QuerySet,
    When,
)
from django.utils import timezone
from django_filters import (
    BooleanFilter,
    DateFromToRangeFilter,
    FilterSet,
    CharFilter,
)

from incidents.models import Incident

from .utils import get_first_day_prev_month


class IncidentReportFilter(FilterSet):
    incident_date = DateFromToRangeFilter()
    is_incident_finish = BooleanFilter(field_name='is_incident_finish')
    last_month = BooleanFilter(
        method='filter_last_month',
        label='Последний месяц',
        help_text=(
            'Возвращает инциденты с первого числа предыдущего месяца по '
            'сегодняшний день.'
        )
    )
    contractor_name = CharFilter(
        field_name='pole__avr_contractor__contractor_name',
        lookup_expr='exact',
        label='Подрядчик',
        help_text=(
            'Возвращает инциденты с опорой закрепленной за указанным '
            'подрядчиком.'
        )
    )

    class Meta:
        model = Incident
        fields = ('incident_date', 'last_month', 'contractor_name')

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


def apply_incident_duration_min_filter(
    queryset: QuerySet[Incident],
    incident_duration_min: Optional[int],
) -> QuerySet[Incident]:
    if not incident_duration_min or incident_duration_min <= 0:
        return queryset

    threshold_td = timedelta(minutes=incident_duration_min)

    duration_expr = Case(
        When(
            is_incident_finish=True,
            then=F('incident_finish_date') - F('insert_date')
        ),
        default=ExpressionWrapper(
            timezone.now() - F('insert_date'),
            output_field=DurationField()
        ),
        output_field=DurationField()
    )

    return queryset.annotate(duration_seconds=duration_expr).filter(
        duration_seconds__gte=threshold_td
    )
