import time
from typing import Optional

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

    @min_wait_timer(yt_managment_logger)
    @timer(yt_managment_logger)
    def check_unclosed_issues(self, yt_manager: YandexTrackerManager):
        """
        Работа с заявками в YandexTracker с ОТКРЫТЫМ статусом.

        Особенности:
            - Всем открытым заявкам надо выставить is_incident_finish=False.
            - Обновить ответственного диспетчера по каждой задаче.
            - В YandexTracker установить/обновить дедлай SLA, если выставлен
            тип инцидента и добавить его к инциденту.
            - В YandexTracker установить значение просрочен ли SLA.
            - Если выставлен статус "Работы передаыны подрядчику", тогда
            отправляем email на подрядчика.
            - В процессе проверяем правильно ли выставлен шифр опоры и номер
            базовой станции.
        """

        unclosed_issues = yt_manager.unclosed_issues()

        type_of_incident_field: Optional[dict] = (
            yt_manager
            .select_local_field(yt_manager.type_of_incident_local_field_id)
        )
        type_of_incident_field_key = (
            type_of_incident_field['id']) if type_of_incident_field else None

        print(type_of_incident_field_key)
