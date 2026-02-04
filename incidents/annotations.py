from datetime import timedelta

from django.core.cache import cache
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DateTimeField,
    DurationField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    QuerySet,
    Value,
    When,
)
from django.utils import timezone

from monitoring.constants import NORMAL_POLES_CACHE_TIMEOUT
from monitoring.models import DeviceStatus, MSysPoles
from ts.constants import UNDEFINED_CASE

from .constants import (
    AVR_CATEGORY,
    DGU_CATEGORY,
    DGU_SLA_IN_PROGRESS_DEADLINE_IN_HOURS,
    DGU_SLA_WAITING_DEADLINE_IN_HOURS,
    INCIDENT_ACCESS_TO_OBJECT_TYPE,
    INCIDENT_AMS_STRUCTURE_TYPE,
    INCIDENT_DESTRUCTION_OBJECT_TYPE,
    INCIDENT_GOVERMENT_REQUEST_TYPE,
    INCIDENT_VOLS_TYPE,
    POWER_ISSUE_TYPES,
    RVR_CATEGORY,
    RVR_SLA_DEADLINE_IN_HOURS,
)
from .models import Incident, IncidentCategoryRelation


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
        sla_avr_waiting=Case(
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
        sla_rvr_waiting=Case(
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


def annotate_sla_dgu(qs: QuerySet[Incident]) -> QuerySet[Incident]:
    """Аннотация SLA для ДГУ"""
    now = timezone.now()

    in_progress_delta = timedelta(
        hours=DGU_SLA_IN_PROGRESS_DEADLINE_IN_HOURS
    )
    waiting_delta = timedelta(
        hours=DGU_SLA_WAITING_DEADLINE_IN_HOURS
    )

    return qs.annotate(
        dgu_has_start=Case(
            When(dgu_start_date__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        dgu_elapsed=ExpressionWrapper(
            Case(
                When(
                    dgu_start_date__isnull=False,
                    dgu_end_date__isnull=False,
                    then=F('dgu_end_date') - F('dgu_start_date'),
                ),
                When(
                    dgu_start_date__isnull=False,
                    dgu_end_date__isnull=True,
                    then=now - F('dgu_start_date'),
                ),
                default=None,
                output_field=DurationField(),
            ),
            output_field=DurationField(),
        ),

        # Просрочен (> 15 суток)
        sla_dgu_expired=Case(
            When(
                dgu_start_date__isnull=False,
                dgu_elapsed__gt=waiting_delta,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),

        # In progress (< 12 часов)
        sla_dgu_in_progress=Case(
            When(
                dgu_start_date__isnull=False,
                dgu_end_date__isnull=True,
                dgu_elapsed__lt=in_progress_delta,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),

        # Waiting (≥ 12 часов и < 15 суток)
        sla_dgu_waiting=Case(
            When(
                dgu_start_date__isnull=False,
                dgu_end_date__isnull=True,
                dgu_elapsed__gte=in_progress_delta,
                dgu_elapsed__lte=waiting_delta,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),

        # Закрыт вовремя (≤ 15 суток)
        sla_dgu_closed_on_time=Case(
            When(
                dgu_start_date__isnull=False,
                dgu_end_date__isnull=False,
                dgu_elapsed__lte=waiting_delta,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
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


def annotate_incident_types(
    qs: QuerySet[Incident]
) -> QuerySet[Incident]:
    is_power_issue_type_q = Q(pk__isnull=True)
    for name in POWER_ISSUE_TYPES:
        is_power_issue_type_q |= Q(incident_type__name=name)

    return qs.annotate(
        is_power_issue_type=Case(
            When(is_power_issue_type_q, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        is_ams_issue_type=Case(
            When(
                incident_type__name=INCIDENT_AMS_STRUCTURE_TYPE,
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        is_goverment_request_issue_type=Case(
            When(
                incident_type__name=INCIDENT_GOVERMENT_REQUEST_TYPE,
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        is_vols_issue_type=Case(
            When(
                incident_type__name=INCIDENT_VOLS_TYPE,
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        is_object_destruction_issue_type=Case(
            When(
                incident_type__name=INCIDENT_DESTRUCTION_OBJECT_TYPE,
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        is_object_access_issue_type=Case(
            When(
                incident_type__name=INCIDENT_ACCESS_TO_OBJECT_TYPE,
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )


def annotate_incident_categories(
    qs: QuerySet[Incident]
) -> QuerySet[Incident]:
    avr_cat = IncidentCategoryRelation.objects.filter(
        incident_id=OuterRef('pk'),
        category__name=AVR_CATEGORY
    )
    rvr_cat = IncidentCategoryRelation.objects.filter(
        incident_id=OuterRef('pk'),
        category__name=RVR_CATEGORY
    )
    dgu_cat = IncidentCategoryRelation.objects.filter(
        incident_id=OuterRef('pk'),
        category__name=DGU_CATEGORY
    )

    return qs.annotate(
        has_avr_category=Exists(avr_cat),
        has_rvr_category=Exists(rvr_cat),
        has_dgu_category=Exists(dgu_cat),
    )


def annotate_incident_subtypes(
    incidents: QuerySet[Incident]
) -> QuerySet[Incident]:
    """
    Возвращает статистику:
    макрорегион → тип → подтип → количество инцидентов
    """
    return (
        incidents
        .exclude(
            incident_type__isnull=True,
            incident_subtype__isnull=True,
        )
        .values(
            'pole__region__macroregion',
            'incident_type__id',
            'incident_type__name',
            'incident_subtype__id',
            'incident_subtype__name',
        )
        .annotate(
            count=Count('id')
        )
    )
