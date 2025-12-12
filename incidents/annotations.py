from datetime import timedelta

from django.db.models import (
    BooleanField,
    Case,
    DateTimeField,
    DurationField,
    ExpressionWrapper,
    F,
    QuerySet,
    Value,
    When,
)
from django.utils import timezone

from .constants import RVR_SLA_DEADLINE_IN_HOURS


def annotate_sla_avr(qs: QuerySet) -> QuerySet:
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


def annotate_sla_rvr(qs: QuerySet) -> QuerySet:
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
