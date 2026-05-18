from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import F, Max

from core.loggers import incident_logger
from incidents.constants import FINISHED_STATUS_NAMES, INCIDENT_BATCH_SIZE
from incidents.models import Incident, IncidentStatusHistory


class Command(BaseCommand):
    help = (
        'Выставление флага и даты закрытия инцидента у которых последний '
        'статус относится к закрытым, но сам инцидент открыт.'
    )

    def handle(self, *args, **options):
        last_status_subquery = IncidentStatusHistory.objects.values(
            'incident_id'
        ).annotate(
            latest_history_id=Max('id'),
            latest_insert_date=Max('insert_date'),
            latest_status_name=F('status__name')
        ).filter(
            status__name__in=FINISHED_STATUS_NAMES
        ).values(
            'incident_id',
            'latest_insert_date'
        )

        affected_incidents_qs = Incident.objects.filter(
            id__in=last_status_subquery.values('incident_id')
        ).exclude(
            is_incident_finish=True
        )

        finish_dates_map: dict[int, datetime] = {}

        history_data = (
            IncidentStatusHistory.objects
            .filter(
                incident_id__in=affected_incidents_qs.values_list(
                    'id', flat=True
                ),
                status__name__in=FINISHED_STATUS_NAMES
            )
            .values('incident_id')
            .annotate(max_date=Max('insert_date'))
        )

        for item in history_data:
            finish_dates_map[item['incident_id']] = item['max_date']

        updated_count = 0

        for incident in affected_incidents_qs.iterator(
            chunk_size=INCIDENT_BATCH_SIZE
        ):
            finish_date = finish_dates_map.get(incident.id)

            if not finish_date or incident.is_incident_finish:
                continue

            incident.is_incident_finish = True
            incident.incident_finish_date = finish_date

            incident.save(
                update_fields=['is_incident_finish', 'incident_finish_date']
            )
            updated_count += 1

        if updated_count:
            incident_logger.warning(
                'Проверка закрытия инцидентов завершена '
                f'(обновлено: {updated_count} записей).'
            )
