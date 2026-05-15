from django.core.management.base import BaseCommand
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import incident_logger
from incidents.models import Incident


class Command(BaseCommand):
    help = 'Удаление тестовых инцидентов.'

    def handle(self, *args, **kwargs):
        incidents_2_del = Incident.objects.filter(
            code__startswith='TEST-'
        )
        total = incidents_2_del.count()

        with tqdm(
            total=total,
            desc='Удаление тестовых инцидентов',
            colour='red',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as progress_bar:
            incidents_2_del.delete()
            progress_bar.update(total - progress_bar.n)

        incident_logger.info(
            f'Удалено {total} Incident, чей код начинается на "TEST-"'
        )
