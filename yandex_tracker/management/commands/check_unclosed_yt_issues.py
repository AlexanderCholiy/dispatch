import time
from datetime import datetime
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import OuterRef, Prefetch, Subquery

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.wraps import min_wait_timer, timer
from emails.email_parser import email_parser
from incidents.constants import (
    DEFAULT_ERR_STATUS_NAME,
    DEFAULT_GENERATION_STATUS_NAME,
    DEFAULT_NOTIFIED_AVR_STATUS_NAME,
    DEFAULT_NOTIFIED_OP_END_STATUS_NAME,
    DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME,
)
from incidents.models import (
    Incident,
    IncidentStatus,
    IncidentStatusHistory,
    IncidentType
)
from incidents.utils import IncidentManager
from ts.models import BaseStation, Pole
from users.models import Roles, User
from yandex_tracker.auto_emails import AutoEmailsFromYT
from yandex_tracker.constants import YT_ISSUES_DAYS_AGO_FILTER
from yandex_tracker.utils import YandexTrackerManager, yt_manager
from yandex_tracker.validators import check_yt_incident_data

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker, с уведомлениями в Telegram.'

    def handle(self, *args, **kwargs):
        tg_manager.send_startup_notification(__name__)

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
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
                if not first_success_sent and not error_count:
                    tg_manager.send_first_success_notification(__name__)
                    first_success_sent = True

                if error_count and not had_errors_last_time:
                    tg_manager.send_warning_counter_notification(
                        __name__, error_count, total_operations
                    )

                had_errors_last_time = error_count > 0

            finally:
                if err is not None and last_error_type != type(err).__name__:
                    tg_manager.send_error_notification(__name__, err)
                    last_error_type = type(err).__name__

    @min_wait_timer(yt_managment_logger)
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
        yt_emails = AutoEmailsFromYT(yt_manager, email_parser)
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
            Prefetch(
                'status_history',
                queryset=(
                    IncidentStatusHistory.objects.select_related('status')
                    .order_by('-insert_date')
                ),
                to_attr='prefetched_statuses'
            ),
        ).annotate(
            latest_status_date=Subquery(latest_status_subquery)
        ).in_bulk()

        all_incident_types = list(IncidentType.objects.all())
        valid_names_of_types = [tp.name for tp in all_incident_types]
        all_users = User.objects.filter(role=Roles.DISPATCH, is_active=True)
        usernames_in_db = [usr.username for usr in all_users]

        all_poles = {}
        for pole_obj in Pole.objects.all():
            all_poles[pole_obj.pole] = pole_obj

        all_base_stations = {}
        for bs_obj in BaseStation.objects.all():
            all_base_stations[bs_obj.bs_name] = bs_obj

        for index, issue in enumerate(unclosed_issues):
            PrettyPrint.progress_bar_info(
                index, total, 'Обработка открытых заявок:')

            database_id: Optional[int] = issue.get(
                yt_manager.database_global_field_id)
            if not database_id:
                continue

            status_key: str = issue['status']['key']
            issue_key: str = issue['key']

            try:
                incident = incidents_prefetched.get(database_id)
                if not incident:
                    if status_key != yt_manager.error_status_key:
                        comment = (
                            'Неизвестный '
                            f'{yt_manager.database_global_field_id} для '
                            'внутреннего номера инцидента.'
                        )
                        was_status_update = yt_manager.update_issue_status(
                            issue_key,
                            yt_manager.error_status_key,
                            comment
                        )
                        if was_status_update:
                            yt_managment_logger.debug(comment)
                    continue

                last_status_history = None
                if (
                    hasattr(incident, 'prefetched_statuses')
                    and incident.prefetched_statuses
                ):
                    last_status_history = incident.prefetched_statuses[0]

                is_valid_yt_data = check_yt_incident_data(
                    incident=incident,
                    yt_manager=yt_manager,
                    logger=yt_managment_logger,
                    issue=issue,
                    yt_users=yt_users,
                    type_of_incident_field=type_of_incident_field,
                    valid_names_of_types=valid_names_of_types,
                    usernames_in_db=usernames_in_db,
                    all_poles=all_poles,
                    all_base_stations=all_base_stations,
                )

                if not is_valid_yt_data:
                    updated_incidents_counter += 1
                    continue

                # Обработка автоответов (данные автоматически синхронизируются)
                # добавлена дополнительная ошибка от спама, если нарушат
                # переходы в рабочем процессе:
                if (
                    status_key == yt_manager.error_status_key
                    and last_status_history.status.name != (
                        DEFAULT_ERR_STATUS_NAME)
                ):
                    IncidentManager.add_error_status(incident)
                    updated_incidents_counter += 1
                elif status_key == yt_manager.in_work_status_key:
                    IncidentManager.add_in_work_status(
                        incident, 'Диспетчер принял работы в YandexTracker')
                elif (
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
                elif (
                    status_key == (
                        yt_manager.notified_op_issue_in_work_status_key)
                    and last_status_history.status.name != (
                        DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME)
                ):
                    IncidentManager.add_notified_op_status(incident)
                    updated_incidents_counter += 1
                elif (
                    status_key == (
                        yt_manager.notified_op_issue_closed_status_key)
                    and last_status_history.status.name != (
                        DEFAULT_NOTIFIED_OP_END_STATUS_NAME)
                ):
                    IncidentManager.add_notified_op_end_status(incident)
                    updated_incidents_counter += 1
                elif (
                    status_key == (
                        yt_manager.notified_avr_in_work_status_key)
                    and last_status_history.status.name != (
                        DEFAULT_NOTIFIED_AVR_STATUS_NAME)
                ):
                    IncidentManager.add_notified_avr_status(incident)
                    updated_incidents_counter += 1
                elif (
                    status_key == yt_manager.notify_op_issue_in_work_status_key
                    and last_status_history.status.name not in (
                        DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME,
                        DEFAULT_ERR_STATUS_NAME,
                    )
                ):
                    yt_emails.notify_operator_issue_in_work(issue, incident)
                    updated_incidents_counter += 1
                elif (
                    status_key == yt_manager.notify_op_issue_in_work_status_key
                    and last_status_history.status.name in (
                        DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME,
                        DEFAULT_ERR_STATUS_NAME,
                    )
                ):
                    yt_manager.update_issue_status(
                        issue_key, yt_manager.error_status_key,
                        'Ошибка рабочего процесса.'
                    )
                    updated_incidents_counter += 1
                elif (
                    status_key == yt_manager.notify_op_issue_closed_status_key
                    and last_status_history.status.name not in (
                        DEFAULT_NOTIFIED_OP_END_STATUS_NAME,
                        DEFAULT_ERR_STATUS_NAME,
                    )
                ):
                    yt_emails.notify_operator_issue_close(issue, incident)
                    updated_incidents_counter += 1
                elif (
                    status_key == yt_manager.notify_op_issue_closed_status_key
                    and last_status_history.status.name in (
                        DEFAULT_NOTIFIED_OP_END_STATUS_NAME,
                        DEFAULT_ERR_STATUS_NAME,
                    )
                ):
                    yt_manager.update_issue_status(
                        issue_key, yt_manager.error_status_key,
                        'Ошибка рабочего процесса.'
                    )
                    updated_incidents_counter += 1
                elif (
                    status_key == yt_manager.notify_avr_in_work_status_key
                    and last_status_history.status.name not in (
                        DEFAULT_NOTIFIED_AVR_STATUS_NAME,
                        DEFAULT_ERR_STATUS_NAME,
                    )
                ):
                    yt_emails.notify_avr_contractor(issue, incident)
                    updated_incidents_counter += 1
                elif (
                    status_key == yt_manager.notify_avr_in_work_status_key
                    and last_status_history.status.name in (
                        DEFAULT_NOTIFIED_AVR_STATUS_NAME,
                        DEFAULT_ERR_STATUS_NAME,
                    )
                ):
                    yt_manager.update_issue_status(
                        issue_key, yt_manager.error_status_key,
                        'Ошибка рабочего процесса.'
                    )
                    updated_incidents_counter += 1

            except Exception as e:
                yt_managment_logger.exception(e)
                error_count += 1

        yt_managment_logger.debug(
            f'Было обновлено {updated_incidents_counter} инцидентов'
        )

        return total, error_count
