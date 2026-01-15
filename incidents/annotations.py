from datetime import timedelta

from django.core.cache import cache
from django.db.models import (
    BooleanField,
    Case,
    DateTimeField,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    QuerySet,
    Value,
    When,
)
from django.utils import timezone

from monitoring.constants import NORMAL_POLES_CACHE_TIMEOUT
from monitoring.models import DeviceStatus, MSysPoles
from ts.constants import UNDEFINED_CASE

from .constants import POWER_ISSUE_TYPES, RVR_SLA_DEADLINE_IN_HOURS
from .models import Incident


def annotate_sla_avr(qs: QuerySet[Incident]) -> QuerySet[Incident]:
    """Аннотация SLA для АВР."""
    now = timezone.now()
    return qs.annotate(
        avr_has_start=Case(
            When(avr_start_date__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        avr_deadline=ExpressionWrapper(
            Case(
                When(
                    incident_type__sla_deadline__isnull=False,
                    avr_start_date__isnull=False,
                    then=F('avr_start_date') + ExpressionWrapper(
                        (
                            timedelta(minutes=1)
                            * F('incident_type__sla_deadline')
                        ),
                        output_field=DurationField()
                    )
                ),
                default=None,
                output_field=DateTimeField()
            ),
            output_field=DateTimeField()
        ),
        sla_avr_expired=Case(
            When(
                incident_type__sla_deadline__isnull=False,
                avr_start_date__isnull=False,
                avr_end_date__isnull=False,
                avr_end_date__gt=F('avr_deadline'),
                then=Value(True)
            ),
            When(
                incident_type__sla_deadline__isnull=False,
                avr_start_date__isnull=False,
                avr_end_date__isnull=True,
                avr_deadline__lt=now,
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        ),
        sla_avr_less_than_hour=Case(
            When(
                incident_type__sla_deadline__isnull=False,
                avr_start_date__isnull=False,
                avr_end_date__isnull=True,
                avr_deadline__gt=now,
                avr_deadline__lte=now + timedelta(hours=1),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        ),
        sla_avr_in_progress=Case(
            When(
                incident_type__sla_deadline__isnull=False,
                avr_start_date__isnull=False,
                avr_end_date__isnull=True,
                avr_deadline__gt=now + timedelta(hours=1),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        ),
        sla_avr_closed_on_time=Case(
            When(
                incident_type__sla_deadline__isnull=False,
                avr_start_date__isnull=False,
                avr_end_date__isnull=False,
                avr_end_date__lte=F('avr_deadline'),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        )
    )


def annotate_sla_rvr(qs: QuerySet[Incident]) -> QuerySet[Incident]:
    """Аннотация SLA для РВР."""
    now = timezone.now()
    return qs.annotate(
        rvr_has_start=Case(
            When(rvr_start_date__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        rvr_deadline=ExpressionWrapper(
            Case(
                When(
                    rvr_start_date__isnull=False,
                    then=(
                        F('rvr_start_date')
                        + timedelta(hours=RVR_SLA_DEADLINE_IN_HOURS)
                    )
                ),
                default=None,
                output_field=DateTimeField()
            ),
            output_field=DateTimeField()
        ),
        sla_rvr_expired=Case(
            When(
                rvr_start_date__isnull=False,
                rvr_end_date__isnull=False,
                rvr_end_date__gt=F('rvr_deadline'),
                then=Value(True)
            ),
            When(
                rvr_start_date__isnull=False,
                rvr_end_date__isnull=True,
                rvr_deadline__lt=now,
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        ),
        sla_rvr_less_than_hour=Case(
            When(
                rvr_start_date__isnull=False,
                rvr_end_date__isnull=True,
                rvr_deadline__gt=now,
                rvr_deadline__lte=now + timedelta(hours=1),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        ),
        sla_rvr_in_progress=Case(
            When(
                rvr_start_date__isnull=False,
                rvr_end_date__isnull=True,
                rvr_deadline__gt=now + timedelta(hours=1),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        ),
        sla_rvr_closed_on_time=Case(
            When(
                rvr_start_date__isnull=False,
                rvr_end_date__isnull=False,
                rvr_end_date__lte=F('rvr_deadline'),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField()
        ),
    )


def annotate_is_power_issue(
    qs: QuerySet[Incident], monitoring_check: bool = True
) -> QuerySet[Incident]:
    """
    Аннотация для инцидента, у которого проблема с питанием на опоре, с
    дополнительной проверкой в мониторинге.
    """
    qs = qs.annotate(
        is_power_issue_candidate=Case(
            When(
                Q(incident_type__name__in=POWER_ISSUE_TYPES)
                & Q(pole__isnull=False)
                & ~Q(pole__pole=UNDEFINED_CASE),
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        )
    )

    if not monitoring_check:
        return qs.annotate(
            is_power_issue=F('is_power_issue_candidate')
        )

    # Данные берутся из сторонней БД:
    normal_poles = cache.get('normal_poles')
    if normal_poles is None:
        normal_poles = frozenset(
            MSysPoles.objects.filter(
                status_id=DeviceStatus.POLE_NORMAL_0
            ).values_list('pole', flat=True)
        )

        cache.set(
            'normal_poles', normal_poles, timeout=NORMAL_POLES_CACHE_TIMEOUT
        )

    return qs.annotate(
        is_power_issue=Case(
            When(
                Q(is_power_issue_candidate=True)
                & ~Q(pole__pole__in=normal_poles),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        )
    )
