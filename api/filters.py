import django_filters
from dateutil.relativedelta import relativedelta
from django.db.models import QuerySet
from django.utils import timezone

from incidents.models import Incident


class IncidentFilter(django_filters.FilterSet):
    incident_date = django_filters.DateFromToRangeFilter()
    last_month = django_filters.BooleanFilter(method='filter_last_month')

    class Meta:
        model = Incident
        fields = ('incident_date', 'last_month')

    def filter_last_month(
        self, queryset: QuerySet[Incident], name: str, value: bool
    ):
        """Заявки с первого числа предыдущего месяца по сегодня"""
        if value:
            now = timezone.localtime(timezone.now())
            first_day_prev_month = (
                now.replace(day=1) - relativedelta(months=1)
            ).replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(
                incident_date__gte=first_day_prev_month,
                incident_date__lte=now
            )
        return queryset
