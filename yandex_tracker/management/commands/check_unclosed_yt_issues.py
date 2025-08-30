import time
from typing import Optional
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.wraps import min_wait_timer, timer
from incidents.constants import (
    DEFAULT_END_STATUS_DESC,
    DEFAULT_END_STATUS_NAME,
)
from incidents.models import Incident, IncidentStatus
from yandex_tracker.utils import YandexTrackerManager, yt_manager
from yandex_tracker.validators import check_yt_incident_data

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

    def handle(self, *args, **kwargs):
        # while True:
        # try:
        self.check_unclosed_issues(yt_manager)
        # except KeyboardInterrupt:
        #     return
        # except Exception as e:
        #     yt_managment_logger.critical(e, exc_info=True)
        #     time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)

    # @min_wait_timer(yt_managment_logger)
    @timer(yt_managment_logger)
    def check_unclosed_issues(self, yt_manager: YandexTrackerManager):
        """
        Работа с заявками в YandexTracker с ОТКРЫТЫМ статусом.

        Особенности:
            - Валидировать номер базовой станции, шифр опоры, подрядчика по
            АВР, операторов на базовой станции и синхронизировать данные с
            базой данных (приоритет у YandexTracker).
            - Обновить ответственного диспетчера по каждой задаче.
            - Всем открытым заявкам надо выставить is_incident_finish=False.
            - В YandexTracker установить/обновить дедлай SLA, если выставлен
            тип инцидента и добавить его к инциденту.
            - В YandexTracker установить значение просрочен ли SLA.
            - Если выставлен статус "Работы передаыны подрядчику", тогда
            отправляем email на подрядчика.
            - В процессе проверяем правильно ли выставлен шифр опоры и номер
            базовой станции.
        """

        unclosed_issues = yt_manager.unclosed_issues()
        yt_users = yt_manager.real_users_in_yt_tracker

        type_of_incident_field: Optional[dict] = (
            yt_manager
            .select_local_field(yt_manager.type_of_incident_local_field_id)
        )
        type_of_incident_field_key = (
            type_of_incident_field['id']) if type_of_incident_field else None

        for index, issue in enumerate(unclosed_issues):
            database_id: Optional[int] = issue.get(
                yt_manager.database_global_field_id)
            if not database_id:
                continue

            user: Optional[dict] = issue.get('assignee')
            issue_key: str = issue['key']
            sla_deadline: Optional[datetime] = issue.get(
                yt_manager.sla_deadline_global_field_id)
            type_of_incident: Optional[str] = issue.get(
                type_of_incident_field_key
            ) if type_of_incident_field_key else None
            status_key: str = issue['status']['key']

            is_valid_yt_data = check_yt_incident_data(
                yt_manager,
                yt_managment_logger,
                issue,
                yt_users,
                type_of_incident_field,
            )

            if not is_valid_yt_data:
                continue
