import time
from datetime import timedelta
from functools import partial
from typing import Callable, Optional

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
from core.threads import tasks_in_threads
from core.wraps import min_wait_timer, timer
from emails.email_parser import email_parser
from emails.models import EmailMessage
from incidents.constants import (
    ERR_STATUS_NAME,
    IN_WORK_STATUS_NAME,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFIED_OP_END_STATUS_NAME,
    NOTIFIED_OP_IN_WORK_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_NAME,
    NOTIFY_OP_END_STATUS_NAME,
    NOTIFY_OP_IN_WORK_STATUS_NAME,
    WAIT_ACCEPTANCE_STATUS_NAME,
)
from incidents.models import (
    Incident,
    IncidentCategory,
    IncidentStatusHistory,
    IncidentType,
)
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
    __name__, YANDEX_TRACKER_ROTATING_FILE
).get_logger()


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker, с уведомлениями в Telegram.'

    min_wait = 5

    cache_timer = 600

    _pole_names_sorted_cache = None
    _pole_names_sorted_cache_last_update = 0

    _valid_names_of_types_cache = None
    _valid_names_of_types_cache_last_update = 0

    _valid_names_of_categories_cache = None
    _valid_names_of_categories_cache_last_update = 0

    _usernames_in_db_cache = None
    _usernames_in_db_cache_last_update = 0

    _all_base_stations_cache = None
    _all_base_stations_last_update = 0

    _devices_by_pole_cache = None
    _devices_by_pole_last_update = 0

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

    def _get_pole_names_sorted_from_cache(self):
        if (
            self._pole_names_sorted_cache is None
            or (
                time.time()
                - self._pole_names_sorted_cache_last_update > self.cache_timer
            )
        ):
            self._pole_names_sorted_cache = list(
                Pole.objects.order_by('pole').values_list('pole', flat=True)
            )
            self._pole_names_sorted_cache_last_update = time.time()
        return self._pole_names_sorted_cache

    def _get_valid_names_of_types_from_cache(self):
        if (
            self._valid_names_of_types_cache is None
            or (
                time.time()
                - self._valid_names_of_types_cache_last_update
                > self.cache_timer
            )
        ):
            self._valid_names_of_types_cache = list(
                IncidentType.objects.all().values_list('name', flat=True)
            )
            self._valid_names_of_types_cache_last_update = time.time()
        return self._valid_names_of_types_cache

    def _get_valid_names_of_categories_from_cache(self):
        if (
            self._valid_names_of_categories_cache is None
            or (
                time.time()
                - self._valid_names_of_categories_cache_last_update
                > self.cache_timer
            )
        ):
            self._valid_names_of_categories_cache = list(
                IncidentCategory.objects.all().values_list('name', flat=True)
            )
            self._valid_names_of_categories_cache_last_update = time.time()
        return self._valid_names_of_categories_cache

    def _get_usernames_in_db_from_cache(self):
        if (
            self._usernames_in_db_cache is None
            or (
                time.time()
                - self._usernames_in_db_cache_last_update > self.cache_timer
            )
        ):
            self._usernames_in_db_cache = list(
                User.objects
                .filter(role=Roles.DISPATCH)
                .values_list('username', flat=True)
            )
            self._usernames_in_db_cache_last_update = time.time()
        return self._usernames_in_db_cache

    def _get_all_base_stations_from_cache(self):
        if (
            self._all_base_stations_cache is None
            or (
                time.time()
                - self._all_base_stations_last_update > self.cache_timer
            )
        ):
            self._all_base_stations_cache = {
                (bs.bs_name, bs.pole.pole if bs.pole else None): bs
                for bs in BaseStation.objects.select_related('pole').all()
            }
            self._all_base_stations_last_update = time.time()
        return self._all_base_stations_cache

    def _get_devices_by_pole_from_cache(self):
        """Оборудование мониторинга"""
        if (
            self._devices_by_pole_cache is None
            or (
                time.time()
                - self._devices_by_pole_last_update > self.cache_timer
            )
        ):
            pole_codes = self._pole_names_sorted_cache or []

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

            self._devices_by_pole_cache: dict[str, list] = {}
            for dev in all_devices:
                for pole in (
                    dev['pole_1__pole'],
                    dev['pole_2__pole'],
                    dev['pole_3__pole'],
                ):
                    if pole:
                        self._devices_by_pole_cache.setdefault(
                            pole.strip(), []
                        ).append(dev)

            self._devices_by_pole_last_update = time.time()
        return self._devices_by_pole_cache

    @min_wait_timer(yt_managment_logger, min_wait)
    @timer(yt_managment_logger)
    def check_unclosed_issues(self) -> tuple[int, int, int]:
        yt_users = yt_manager.real_users_in_yt_tracker
        type_of_incident_field: dict = (
            yt_manager
            .select_local_field(yt_manager.type_of_incident_local_field_id)
        )
        category_field: dict = (
            yt_manager.select_local_field(yt_manager.category_local_field_id)
        )

        pole_names_sorted = self._get_pole_names_sorted_from_cache()
        valid_names_of_types = self._get_valid_names_of_types_from_cache()
        valid_names_of_categories = (
            self._get_valid_names_of_categories_from_cache()
        )
        usernames_in_db = self._get_usernames_in_db_from_cache()
        all_base_stations = self._get_all_base_stations_from_cache()

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
                    category_field=category_field,
                    valid_names_of_categories=valid_names_of_categories,
                    usernames_in_db=usernames_in_db,
                    pole_names_sorted=pole_names_sorted,
                    all_base_stations=all_base_stations,
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
        category_field: dict,
        valid_names_of_categories: list[str],
        usernames_in_db: list[str],
        pole_names_sorted: list[str],
        all_base_stations: dict[tuple[str, Optional[str]], BaseStation],
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
            'responsible_user',
            'pole__region',
            'pole__region__rvr_email',
        ).prefetch_related(
            'statuses',
            'categories',
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

        validation_tasks = []
        incidents_2_update = []

        for index, issue in enumerate(unclosed_issues):
            PrettyPrint.progress_bar_info(
                index, total,
                f'Обработка открытых заявок (стр.{batch_number}):'
            )

            database_id: Optional[int] = issue.get(
                yt_manager.database_global_field_id
            )

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
                    category_field=category_field,
                    valid_names_of_categories=valid_names_of_categories,
                    usernames_in_db=usernames_in_db,
                    pole_names_sorted=pole_names_sorted,
                    all_base_stations=all_base_stations,
                    devices_by_pole=self._get_devices_by_pole_from_cache(),
                )

                if not is_valid_yt_data:
                    if update_data_func:
                        validation_tasks.append(update_data_func)

                    if update_status_func:
                        validation_tasks.append(update_status_func)

                    updated_incidents_counter += 1
                    continue

                if not last_status_history:
                    IncidentManager.add_default_status(incident)
                    continue

                can_send, timeout_send = self._anti_spam_check(
                    last_status_history,
                    NOTIFY_SPAM_DELAY,
                    (
                        NOTIFY_OP_IN_WORK_STATUS_NAME,
                        NOTIFY_CONTRACTOR_STATUS_NAME,
                        NOTIFY_OP_END_STATUS_NAME,

                    )
                )

                # Проверка запрещенных статусов для заявок созданных вручную:
                if not incident.is_auto_incident and status_key in (
                    yt_manager.notify_op_issue_in_work_status_key,
                    yt_manager.notify_op_issue_closed_status_key,
                ):
                    if status_key == (
                        yt_manager.notify_op_issue_in_work_status_key
                    ):
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Нельзя отправить автоматическое '
                                    'уведомление заявителю о принятии заявки '
                                    'в работу, т.к. она была создана вручную.'
                                )
                            )
                        )
                    elif status_key == (
                        yt_manager.notify_op_issue_closed_status_key
                    ):
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Нельзя отправить автоматическое '
                                    'уведомление заявителю о закрытии заявки, '
                                    'т.к. она была создана вручную.'
                                )
                            )
                        )

                    continue

                # Защита от частого перехода между статусами:
                if not can_send:
                    if status_key == (
                        yt_manager.notify_op_issue_in_work_status_key
                    ):
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Информация о принятии работ недавно '
                                    'была отправлено заявителю. '
                                    f'Попробуйте снова через {timeout_send} '
                                    'секунд.'
                                )
                            )
                        )
                    elif status_key == (
                        yt_manager.notify_op_issue_closed_status_key
                    ):
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Информация о закрытии работ уже была '
                                    'отправлена заявителю.'
                                    f'Попробуйте снова через {timeout_send} '
                                    'секунд.'
                                )
                            )
                        )
                    elif status_key == (
                        yt_manager.notify_contractor_in_work_status_key
                    ):
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Информация об инциденте уже была '
                                    'передана в работу подрядчику. '
                                    f'Попробуйте снова через {timeout_send} '
                                    'секунд.'
                                )
                            )
                        )

                    continue

                # Задачи необходимо выполнять в едином цикле, т.к. методы
                # класса AutoEmailsFromYT необходимо вызывать сразу.
                yt_auto_emails = AutoEmailsFromYT(
                    yt_manager, email_parser, issue, incident
                )

                if (
                    status_key == yt_manager.error_status_key
                    and last_status_history.status.name != ERR_STATUS_NAME
                ):
                    IncidentManager.add_error_status(incident)
                elif (
                    status_key == yt_manager.need_acceptance_status_key
                    and last_status_history.status.name != (
                        WAIT_ACCEPTANCE_STATUS_NAME
                    )
                ):
                    IncidentManager.add_wait_acceptance_status(incident)
                elif (
                    status_key == yt_manager.in_work_status_key
                    and last_status_history.status.name != IN_WORK_STATUS_NAME
                ):
                    IncidentManager.add_in_work_status(
                        incident, 'Диспетчер принял работы в YandexTracker'
                    )
                elif (
                    status_key == (
                        yt_manager.notified_op_issue_in_work_status_key
                    )
                    and last_status_history.status.name != (
                        NOTIFIED_OP_IN_WORK_STATUS_NAME
                    )
                ):
                    IncidentManager.add_notified_op_status(incident)
                elif (
                    status_key == (
                        yt_manager.notified_op_issue_closed_status_key
                    )
                    and last_status_history.status.name != (
                        NOTIFIED_OP_END_STATUS_NAME
                    )
                ):
                    IncidentManager.add_notified_op_end_status(incident)

                elif (
                    status_key == (
                        yt_manager.notified_contractor_in_work_status_key
                    )
                    and last_status_history.status.name != (
                        NOTIFIED_CONTRACTOR_STATUS_NAME
                    )
                ):
                    IncidentManager.add_notified_contractor_status(incident)
                elif status_key == (
                    yt_manager.notify_op_issue_in_work_status_key
                ):
                    if last_status_history.status.name not in (
                        NOTIFIED_OP_IN_WORK_STATUS_NAME,
                        NOTIFY_OP_IN_WORK_STATUS_NAME,
                    ):
                        yt_auto_emails.notify_operator_issue_in_work()
                    else:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Автоматическое уведомление о принятии '
                                    'заявки в работу недавно было отправлено '
                                    'заявителю.'
                                )
                            )
                        )

                elif status_key == (
                    yt_manager.notify_op_issue_closed_status_key
                ):
                    if last_status_history.status.name not in (
                        NOTIFIED_OP_END_STATUS_NAME,
                        NOTIFY_OP_END_STATUS_NAME,
                    ):
                        yt_auto_emails.notify_issue_close(category_field)
                    else:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Автоматическое уведомление о закрытии '
                                    'заявки недавно было отправлено.'
                                )
                            )
                        )

                elif status_key == (
                    yt_manager.notify_contractor_in_work_status_key
                ):
                    if last_status_history.status.name not in (
                        NOTIFIED_CONTRACTOR_STATUS_NAME,
                        NOTIFY_CONTRACTOR_STATUS_NAME,
                    ):
                        yt_auto_emails.notify_contractors(category_field)
                    else:
                        validation_tasks.append(
                            partial(
                                yt_manager.update_issue_status,
                                issue_key,
                                yt_manager.error_status_key,
                                (
                                    'Автоматическое уведомление о передаче '
                                    'заявки подрядчику недавно было '
                                    'отправлено.'
                                )
                            )
                        )

                updated_avr_rvr_date = (
                    IncidentManager.auto_update_avr_rvr_dates(incident)
                )

                if updated_avr_rvr_date:
                    incidents_2_update.append(incident)

            except Exception as e:
                yt_managment_logger.exception(e)
                error_count += 1

        if incidents_2_update:
            Incident.objects.bulk_update(
                incidents_2_update,
                [
                    'avr_start_date',
                    'avr_end_date',
                    'rvr_start_date',
                    'rvr_end_date',
                ]
            )

        return total, error_count, updated_incidents_counter, validation_tasks

    def _anti_spam_check(
        self,
        last_status_history: IncidentStatusHistory,
        delay: timedelta,
        allowed_status_names: tuple[str]
    ) -> tuple[bool, int]:
        """
        Проверяет, можно ли повторно отправлять автоуведомление,
        чтобы избежать спама при частых переходах между статусами.

        Args:
            last_status_history (IncidentStatusHistory):
                Последняя запись истории статусов для инцидента.
            delay (timedelta):
                Минимальный интервал между отправками автоуведомлений.

        Returns:
            tuple[bool, int]:
                - bool — можно ли отправлять уведомление;
                - int — количество секунд, через сколько можно будет
                отправить автоответ (0, если уже можно).
        """
        if last_status_history.status.name not in allowed_status_names:
            return True, 0

        delta: timedelta = timezone.now() - last_status_history.insert_date
        timeout = max(int((delay - delta).total_seconds()), 0)

        return delta > delay, timeout
