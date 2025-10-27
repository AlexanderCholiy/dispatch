import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from numpy import nan

from core.constants import INCIDENTS_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.wraps import timer
from incidents.constants import (
    AVR_CATEGORY,
    DEFAULT_STATUS_DESC,
    DEFAULT_STATUS_NAME,
    END_STATUS_DESC,
    END_STATUS_NAME,
    ERR_STATUS_DESC,
    ERR_STATUS_NAME,
    GENERATION_STATUS_DESC,
    GENERATION_STATUS_NAME,
    IN_WORK_STATUS_DESC,
    IN_WORK_STATUS_NAME,
    INCIDENT_CATEGORIES_FILE,
    INCIDENT_STATUSES_FILE,
    INCIDENT_TYPES_FILE,
    NOTIFIED_CONTRACTOR_STATUS_DESC,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFIED_OP_END_STATUS_DESC,
    NOTIFIED_OP_END_STATUS_NAME,
    NOTIFIED_OP_IN_WORK_STATUS_DESC,
    NOTIFIED_OP_IN_WORK_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_DESC,
    NOTIFY_CONTRACTOR_STATUS_NAME,
    NOTIFY_OP_END_STATUS_DESC,
    NOTIFY_OP_END_STATUS_NAME,
    NOTIFY_OP_IN_WORK_STATUS_DESC,
    NOTIFY_OP_IN_WORK_STATUS_NAME,
    RVR_CATEGORY,
    WAIT_ACCEPTANCE_STATUS_DESC,
    WAIT_ACCEPTANCE_STATUS_NAME,
)
from incidents.models import (
    IncidentCategory,
    IncidentCategoryRelation,
    IncidentStatus,
    IncidentStatusHistory,
    IncidentType,
)

incident_managment_logger = LoggerFactory(
    __name__, INCIDENTS_LOG_ROTATING_FILE
).get_logger()


class Command(BaseCommand):
    help = 'Заполнение дефолтными значениями IncidentStatus и IncidentType.'

    def handle(self, *args, **kwargs):
        self.update_incident_types()
        self.update_incident_category()
        self.update_incident_statuses()

    @timer(incident_managment_logger)
    def update_incident_types(self):
        incident_types = pd.read_excel(INCIDENT_TYPES_FILE)
        incident_types.replace('', None, inplace=True)
        incident_types.replace(nan, None, inplace=True)

        incident_types['name'] = incident_types['name'].astype(str)
        incident_types['description'] = (
            incident_types['description'].astype(str))
        incident_types['sla_deadline'] = (
            incident_types['sla_deadline'].astype(int))

        total = len(incident_types)

        for index, row in incident_types.iterrows():
            PrettyPrint.progress_bar_debug(
                index, total, 'Обновление IncidentType:'
            )
            name = str(row['name']).strip() or None
            description = str(row['description']).strip() or None
            sla_deadline = row['sla_deadline'] or None

            if not isinstance(sla_deadline, int) or not name:
                continue

            if not IncidentType.objects.filter(name=name).exists():
                IncidentType.objects.create(
                    name=name,
                    description=description,
                    sla_deadline=sla_deadline,
                )

    @timer(incident_managment_logger)
    @transaction.atomic()
    def update_incident_statuses(self):
        default_statuses = [
            (DEFAULT_STATUS_NAME, DEFAULT_STATUS_DESC),
            (END_STATUS_NAME, END_STATUS_DESC),
            (ERR_STATUS_NAME, ERR_STATUS_DESC),
            (WAIT_ACCEPTANCE_STATUS_NAME, WAIT_ACCEPTANCE_STATUS_DESC),
            (GENERATION_STATUS_NAME, GENERATION_STATUS_DESC),
            (IN_WORK_STATUS_NAME, IN_WORK_STATUS_DESC),
            (NOTIFY_OP_IN_WORK_STATUS_NAME, NOTIFY_OP_IN_WORK_STATUS_DESC),
            (NOTIFIED_OP_IN_WORK_STATUS_NAME, NOTIFIED_OP_IN_WORK_STATUS_DESC),
            (NOTIFY_OP_END_STATUS_NAME, NOTIFY_OP_END_STATUS_DESC),
            (NOTIFIED_OP_END_STATUS_NAME, NOTIFIED_OP_END_STATUS_DESC),
            (NOTIFY_CONTRACTOR_STATUS_NAME, NOTIFY_CONTRACTOR_STATUS_DESC),
            (NOTIFIED_CONTRACTOR_STATUS_NAME, NOTIFIED_CONTRACTOR_STATUS_DESC),
        ]

        total = len(default_statuses)

        for index, (name, description) in enumerate(default_statuses):
            PrettyPrint.progress_bar_info(
                index, total,
                'Обновление значений по умолчанию в IncidentStatus:'
            )
            IncidentStatus.objects.get_or_create(
                name=name,
                defaults={'description': description},
            )

        incident_statuses = pd.read_excel(INCIDENT_STATUSES_FILE)
        incident_statuses.replace('', None, inplace=True)
        incident_statuses.replace(nan, None, inplace=True)

        incident_statuses['name'] = incident_statuses['name'].astype(str)
        incident_statuses['description'] = (
            incident_statuses['description'].astype(str)
        )

        total = len(incident_statuses)

        for index, row in incident_statuses.iterrows():
            PrettyPrint.progress_bar_info(
                index, total, 'Обновление IncidentStatus:'
            )
            name = str(row['name']).strip() or None
            description = str(row['description']).strip() or None

            if not name:
                continue

            IncidentStatus.objects.get_or_create(
                name=name,
                defaults={'description': description},
            )

        valid_status_ids = set(
            IncidentStatus.objects.values_list('id', flat=True)
        )
        incident_history = IncidentStatusHistory.objects.all()
        total = len(incident_history)
        for index, history in enumerate(incident_history):
            PrettyPrint.progress_bar_error(
                index, total,
                'Удаление не актуальных связей в IncidentStatusHistory:'
            )
            if history.status_id not in valid_status_ids:
                history.delete()

    @timer(incident_managment_logger)
    @transaction.atomic()
    def update_incident_category(self):
        incident_categories = pd.read_excel(INCIDENT_CATEGORIES_FILE)
        incident_categories.replace('', None, inplace=True)
        incident_categories.replace(nan, None, inplace=True)

        incident_categories['name'] = incident_categories['name'].astype(str)
        incident_categories['description'] = (
            incident_categories['description'].astype(str)
        )

        total = len(incident_categories)

        for index, row in incident_categories.iterrows():
            PrettyPrint.progress_bar_success(
                index, total, 'Обновление IncidentCategory:'
            )
            name = str(row['name']).strip() or None
            description = str(row['description']).strip() or None

            if not name:
                continue

            if not IncidentCategory.objects.filter(name=name).exists():
                IncidentCategory.objects.create(
                    name=name,
                    description=description,
                )

        for category_name in (AVR_CATEGORY, RVR_CATEGORY):
            IncidentCategory.objects.get_or_create(name=category_name)

        valid_category_ids = set(
            IncidentCategory.objects.values_list('id', flat=True)
        )
        incident_history = IncidentCategoryRelation.objects.all()
        total = len(incident_history)
        for index, history in enumerate(incident_history):
            PrettyPrint.progress_bar_warning(
                index, total,
                'Удаление не актуальных связей в IncidentCategoryRelation:'
            )
            if history.category_id not in valid_category_ids:
                history.delete()
