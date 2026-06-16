from django.db.models import (
    Case,
    CharField,
    QuerySet,
    Value,
    When,
)
from django.utils import timezone

from .models import PlannedWork, PlannedWorkStatus


def annotate_plr_status(qs: QuerySet[PlannedWork]) -> QuerySet[PlannedWork]:
    """Аннотация статуса для ПЛР."""
    now = timezone.now()

    return qs.annotate(
        current_status=Case(
            When(
                end_date__isnull=False,
                end_date__lte=now,
                then=Value(PlannedWorkStatus.COMPLETED)
            ),
            When(
                start_date__lte=now,
                then=Value(PlannedWorkStatus.IN_PROGRESS)
            ),
            default=Value(PlannedWorkStatus.PLANNED),
            output_field=CharField()
        ),
    )
