import time
from typing import Optional
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import OuterRef, Subquery

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
    DEFAULT_GENERATION_STATUS_NAME,
)
from yandex_tracker.constants import YT_ISSUES_DAYS_AGO_FILTER
from incidents.utils import IncidentManager
from incidents.models import Incident, IncidentStatus, IncidentStatusHistory
from yandex_tracker.utils import YandexTrackerManager, yt_manager
from yandex_tracker.validators import check_yt_incident_data
from core.tg_bot import tg_manager

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker, с уведомлениями в Telegram.'

    def handle(self, *args, **kwargs):
        # tg_manager.send_startup_notification(__name__)

        first_success_sent = False
        had_errors_last_time = False
        last_error_type = None

        while True:
            err = None
            error_count = 0
            total_operations = 0

            try:
                total_operations, error_count = self.check_unclosed_issues(
                    yt_manager)
            except KeyboardInterrupt:
                return
            except Exception as e:
                yt_managment_logger.critical(e, exc_info=True)
                err = e
                # time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
                if not first_success_sent and not error_count:
                    # tg_manager.send_first_success_notification(__name__)
                    first_success_sent = True

                # if error_count and not had_errors_last_time:
                #     tg_manager.send_warning_counter_notification(
                #         __name__, error_count, total_operations
                #     )

                had_errors_last_time = error_count > 0

            finally:
                if err is not None and last_error_type != type(err).__name__:
                    # tg_manager.send_error_notification(__name__, err)
                    last_error_type = type(err).__name__

    # @min_wait_timer(yt_managment_logger)
    @timer(yt_managment_logger)
    def check_unclosed_issues(self, yt_manager: YandexTrackerManager) -> tuple:
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
            - В YandexTracker установить статус SLA.
            - Если выставлен статус "Передать работы подрядчику", тогда
            отправляем email на подрядчика и меняем статус на
            "Работы переданы подрядчику".

        Returns:
            tuple: общее кол-во операций и кол-во ошибок.
        """

        unclosed_issues = yt_manager.unclosed_issues(YT_ISSUES_DAYS_AGO_FILTER)
        total = len(unclosed_issues)
        yt_users = yt_manager.real_users_in_yt_tracker

        type_of_incident_field: dict = (
            yt_manager
            .select_local_field(yt_manager.type_of_incident_local_field_id)
        )
        updated_incidents_counter = 0

        error_count = 0

        database_ids = []
        for issue in unclosed_issues:
            database_id = issue.get(yt_manager.database_global_field_id)
            if database_id:
                database_ids.append(database_id)

        latest_status_subquery = IncidentStatusHistory.objects.filter(
            incident=OuterRef('pk')
        ).order_by('-insert_date').values('insert_date')[:1]

        incidents_prefetched = Incident.objects.filter(
            id__in=database_ids
        ).select_related(
            'incident_type',
            'pole',
            'pole__avr_contractor',
            'base_station',
            'responsible_user'
        ).prefetch_related(
            'statuses',
            'base_station__operator',
        ).annotate(
            latest_status_date=Subquery(latest_status_subquery)
        ).in_bulk()  # Создаем словарь {id: incident}

        for index, issue in enumerate(unclosed_issues):
            # PrettyPrint.progress_bar_info(
            #     index, total, 'Обработка открытых заявок:')

            database_id: Optional[int] = issue.get(
                yt_manager.database_global_field_id)
            if not database_id:
                continue

            status_key: str = issue['status']['key']

            try:
                is_valid_yt_data = check_yt_incident_data(
                    yt_manager,
                    yt_managment_logger,
                    issue,
                    yt_users,
                    type_of_incident_field,
                )

                if not is_valid_yt_data:
                    updated_incidents_counter += 1
                    continue

                incident = Incident.objects.get(pk=database_id)
                last_status_history = IncidentStatusHistory.objects.filter(
                    incident=incident
                ).order_by('-pk').first()

                incident = incidents_prefetched.get(database_id)

                # Синхронизируем данные в базе:
                if status_key == yt_manager.in_work_status_key:
                    IncidentManager.add_in_work_status(
                        incident, 'Диспетчер принял работы в YandexTracker')

                if (
                    status_key == yt_manager.on_generation_status_key
                    and last_status_history.status.name != (
                        DEFAULT_GENERATION_STATUS_NAME)
                ):
                    IncidentManager.add_generation_status(
                        incident,
                        (
                            'Диспетчер указал в YandexTracker, что опора '
                            'находится на генерации.'
                        )
                    )

            except Exception as e:
                yt_managment_logger.exception(e)
                error_count += 1

            print(status_key)

        yt_managment_logger.debug(
            f'Было обновлено {updated_incidents_counter} инцидентов'
        )

        return total, error_count
