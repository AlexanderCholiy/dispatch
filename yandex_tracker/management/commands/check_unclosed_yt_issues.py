import time
import os
from datetime import timedelta
from typing import Optional, Callable
from functools import partial
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.utils import timezone

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.wraps import min_wait_timer, timer
from core.threads import tasks_in_threads
from emails.email_parser import email_parser
from emails.models import EmailMessage
from incidents.constants import (
    DEFAULT_ERR_STATUS_NAME,
    DEFAULT_NOTIFIED_AVR_STATUS_NAME,
    DEFAULT_NOTIFIED_OP_END_STATUS_NAME,
    DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME,
    DEFAULT_NOTIFY_AVR_STATUS_NAME,
    DEFAULT_WAIT_ACCEPTANCE_STATUS_NAME,
)
from incidents.models import Incident, IncidentStatusHistory, IncidentType
from incidents.utils import IncidentManager
from monitoring.models import MSysModem
from ts.models import BaseStation, Pole, PoleContractorEmail
from users.models import Roles, User
from yandex_tracker.auto_emails import AutoEmailsFromYT
from yandex_tracker.constants import (
    NOTIFY_SPAM_DELAY,
    YT_ISSUES_DAYS_AGO_FILTER,
)
from yandex_tracker.utils import YandexTrackerManager, yt_manager
from yandex_tracker.validators import check_yt_incident_data

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker, с уведомлениями в Telegram.'

    min_wait = 1

    def handle(self, *args, **kwargs):
        tg_manager.send_startup_notification(__name__)

        first_success_sent = False
        had_errors_last_time = False
        last_error_type = None

        while True:
            err = None
            total_errors = 0
            total_operations = 0

            try:
                total_operations, total_errors, total_updated = (
                    self.check_unclosed_issues())
                if total_updated or total_errors:
                    yt_managment_logger.info(
                        f'Обработано {total_operations} инцидент(ов), '
                        f'обновлено {total_updated}, ошибок {total_errors}'
                    )
            except KeyboardInterrupt:
                return
            except Exception as e:
                yt_managment_logger.critical(e, exc_info=True)
                err = e
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
                if not first_success_sent and not total_errors:
                    tg_manager.send_first_success_notification(__name__)
                    first_success_sent = True

                if total_errors and not had_errors_last_time:
                    tg_manager.send_warning_counter_notification(
                        __name__, total_errors, total_operations
                    )

                had_errors_last_time = total_errors > 0

            finally:
                if err is not None and last_error_type != type(err).__name__:
                    tg_manager.send_error_notification(__name__, err)
                    last_error_type = type(err).__name__

    @min_wait_timer(yt_managment_logger, min_wait)
    @timer(yt_managment_logger)
    def check_unclosed_issues(self) -> tuple[int, int, int]:
        yt_users = yt_manager.real_users_in_yt_tracker
        yt_emails = AutoEmailsFromYT(yt_manager, email_parser)

        type_of_incident_field: dict = (
            yt_manager
            .select_local_field(yt_manager.type_of_incident_local_field_id)
        )

        pole_names_sorted = [p.pole for p in Pole.objects.order_by('pole')]

        all_incident_types = list(IncidentType.objects.all())
        valid_names_of_types = [tp.name for tp in all_incident_types]
        all_users = User.objects.filter(role=Roles.DISPATCH, is_active=True)
        usernames_in_db = [usr.username for usr in all_users]

        all_base_stations = {
            (bs.bs_name, bs.pole.pole if bs.pole else None): bs
            for bs in BaseStation.objects.select_related('pole').all()
        }

        total_processed = 0
        total_errors = 0
        total_updated = 0
        all_tasks: list[Callable] = []

        unclosed_issues_batches = yt_manager.unclosed_issues(
            YT_ISSUES_DAYS_AGO_FILTER
        )

        for i, unclosed_issues in enumerate(unclosed_issues_batches, 1):
            batch_total, batch_errors, batch_updated, tasks = (
                self.check_unclosed_batch_issues(
                    batch_number=i,
                    yt_manager=yt_manager,
                    unclosed_issues=unclosed_issues,
                    yt_users=yt_users,
                    type_of_incident_field=type_of_incident_field,
                    valid_names_of_types=valid_names_of_types,
                    usernames_in_db=usernames_in_db,
                    pole_names_sorted=pole_names_sorted,
                    all_base_stations=all_base_stations,
                    yt_emails=yt_emails,
                )
            )

            total_processed += batch_total
            total_errors += batch_errors
            total_updated += batch_updated
            all_tasks.extend(tasks)

        tasks_in_threads(all_tasks, yt_managment_logger)

        return total_processed, total_errors, total_updated

    def check_unclosed_batch_issues(
        self,
        batch_number: int,
        yt_manager: YandexTrackerManager,
        unclosed_issues: list[dict],
        yt_users: dict,
        type_of_incident_field: dict,
        valid_names_of_types: list[str],
        usernames_in_db: list[str],
        pole_names_sorted: list[str],
        all_base_stations: dict[tuple[str, Optional[str]], BaseStation],
        yt_emails: AutoEmailsFromYT,
    ) -> tuple[int, int, int, list[Callable]]:
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
            tuple: общее кол-во операций, кол-во ошибок, кол-во обновленных
            задач.
        """
        total = len(unclosed_issues)
        error_count = 0
        updated_incidents_counter = 0

        database_ids = [
            issue.get(yt_manager.database_global_field_id)
            for issue in unclosed_issues
            if issue.get(yt_manager.database_global_field_id)
        ]

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
                'pole__pole_emails',
                queryset=PoleContractorEmail.objects.select_related(
                    'email', 'contractor'
                ),
            ),
            Prefetch(
                'email_messages',
                queryset=EmailMessage.objects.prefetch_related(
                    'email_msg_to',
                    'email_msg_cc',
                ),
            ),
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

        # Оборудование мониторинга:
        pole_codes_in_yt = set([
            issue.get(yt_manager.pole_number_global_field_id)
            for issue in unclosed_issues
        ])

        pole_codes = pole_codes_in_yt & set(pole_names_sorted)

        try:
            all_devices = (
                MSysModem.objects
                .filter(
                    Q(pole_1__pole__in=pole_codes)
                    | Q(pole_2__pole__in=pole_codes)
                    | Q(pole_3__pole__in=pole_codes)
                )
                .select_related('pole_1', 'pole_2', 'pole_3', 'status')
                .values(
                    'modem_ip',
                    'pole_1__pole',
                    'pole_2__pole',
                    'pole_3__pole',
                    'level',
                    'status__id',
                )
            )
        except Exception as e:
            yt_managment_logger.exception(e)
            all_devices = []

        devices_by_pole: dict[str, list] = {}
        for dev in all_devices:
            for pole in (
                dev['pole_1__pole'],
                dev['pole_2__pole'],
                dev['pole_3__pole'],
            ):
                if pole:
                    devices_by_pole.setdefault(pole.strip(), []).append(dev)

        validation_tasks = []

        for index, issue in enumerate(unclosed_issues):
            PrettyPrint.progress_bar_info(
                index, total,
                f'Обработка открытых заявок (стр.{batch_number}):'
            )

            database_id: Optional[int] = issue.get(
                yt_manager.database_global_field_id)

            status_key: str = issue['status']['key']
            issue_key: str = issue['key']

            if not database_id:
                yt_manager.create_incident_from_issue(issue, False)
                continue

            try:
                incident = incidents_prefetched.get(database_id)
                if not incident:
                    if status_key != yt_manager.error_status_key:
                        comment = (
                            'Неизвестный '
                            f'{yt_manager.database_global_field_id} для '
                            'внутреннего номера инцидента.'
                        )
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                comment
                            )
                        )
                    continue

                last_status_history = None
                if (
                    hasattr(incident, 'prefetched_statuses')
                    and incident.prefetched_statuses
                ):
                    last_status_history = incident.prefetched_statuses[0]

                (
                    is_valid_yt_data, update_data_func, update_status_func
                ) = check_yt_incident_data(
                    incident=incident,
                    yt_manager=yt_manager,
                    logger=yt_managment_logger,
                    issue=issue,
                    yt_users=yt_users,
                    type_of_incident_field=type_of_incident_field,
                    valid_names_of_types=valid_names_of_types,
                    usernames_in_db=usernames_in_db,
                    pole_names_sorted=pole_names_sorted,
                    all_base_stations=all_base_stations,
                    devices_by_pole=devices_by_pole,
                )

                if not is_valid_yt_data:
                    if update_data_func:
                        validation_tasks.append(update_data_func)

                    if update_status_func:
                        validation_tasks.append(update_status_func)

                    updated_incidents_counter += 1
                    continue

                # Обработка автоответов (данные автоматически синхронизируются)
                # добавлена дополнительная ошибка от спама, если нарушат
                # переходы в рабочем процессе:
                if last_status_history:
                    delta: timedelta = (
                        timezone.now() - last_status_history.insert_date
                    )
                    check_status_dt = delta >= NOTIFY_SPAM_DELAY
                    timeout = max(
                        int((NOTIFY_SPAM_DELAY - delta).total_seconds()), 0)
                else:
                    IncidentManager.add_default_status(incident)
                    updated_incidents_counter += 1
                    continue

                if (
                    status_key == yt_manager.error_status_key
                    and last_status_history.status.name != (
                        DEFAULT_ERR_STATUS_NAME)
                ):
                    IncidentManager.add_error_status(incident)
                    updated_incidents_counter += 1

                elif (
                    status_key == yt_manager.need_acceptance_status_key
                    and last_status_history.status.name != (
                        DEFAULT_WAIT_ACCEPTANCE_STATUS_NAME
                    )
                ):
                    IncidentManager.add_wait_acceptance_status(incident)
                    updated_incidents_counter += 1

                elif status_key == yt_manager.in_work_status_key:
                    IncidentManager.add_in_work_status(
                        incident, 'Диспетчер принял работы в YandexTracker'
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
                ):
                    if not incident.is_auto_incident:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Нельзя отправить автоматическое '
                                    'уведомление заявителю для заявки, '
                                    'созданной вручную.'
                                )
                            )
                        )
                        updated_incidents_counter += 1
                    elif last_status_history.status.name not in (
                        DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME,
                    ):
                        yt_emails.notify_operator_issue_in_work(
                            issue, incident)
                        updated_incidents_counter += 1
                    elif check_status_dt:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Уведомление о принятии работ недавно '
                                    'было отправлено заявителю. '
                                    f'Попробуйте снова через {timeout} секунд.'
                                )
                            )
                        )
                        updated_incidents_counter += 1

                elif (
                    status_key == yt_manager.notify_op_issue_closed_status_key
                ):
                    if not incident.is_auto_incident:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Нельзя отправить автоматическое '
                                    'уведомление заявителю для заявки, '
                                    'созданной вручную.'
                                )
                            )
                        )
                        updated_incidents_counter += 1
                    elif last_status_history.status.name not in (
                        DEFAULT_NOTIFIED_OP_END_STATUS_NAME,
                    ):
                        yt_emails.notify_operator_issue_close(issue, incident)

                        contractor_emails = IncidentManager.get_avr_emails(
                            incident
                        )

                        incident_emails = IncidentManager.all_incident_emails(
                            incident
                        )

                        incident_status_names: set[str] = {
                            st.name for st in incident.statuses.all()
                        }

                        if (
                            incident.pole
                            and incident.pole.avr_contractor
                            and contractor_emails
                            and (
                                any(
                                    s in incident_status_names for s in (
                                        DEFAULT_NOTIFIED_AVR_STATUS_NAME,
                                        DEFAULT_NOTIFY_AVR_STATUS_NAME,
                                    )
                                )
                                or not set(contractor_emails).isdisjoint(
                                    incident_emails
                                )
                            )
                        ):
                            yt_emails.notify_avr_issue_close(issue, incident)

                        updated_incidents_counter += 1
                    elif check_status_dt:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Уведомление о закрытии работ уже было '
                                    'отправлено заявителю.'
                                    f'Попробуйте снова через {timeout} секунд.'
                                )
                            )
                        )
                        updated_incidents_counter += 1

                elif (
                    status_key == yt_manager.notify_avr_in_work_status_key
                ):
                    if last_status_history.status.name not in (
                        DEFAULT_NOTIFIED_AVR_STATUS_NAME,
                    ):
                        yt_emails.notify_avr_contractor(issue, incident)
                        updated_incidents_counter += 1
                    elif check_status_dt:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Информация об инциденте уже была '
                                    'передана в работу подрядчику. '
                                    f'Попробуйте снова через {timeout} секунд.'
                                )
                            )
                        )
                        updated_incidents_counter += 1

            except Exception as e:
                yt_managment_logger.exception(e)
                error_count += 1

        return total, error_count, updated_incidents_counter, validation_tasks
