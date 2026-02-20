import inspect
import os
import re
import tempfile
import time
from datetime import datetime, timedelta
from http import HTTPMethod, HTTPStatus
from typing import Generator, Optional

import requests
from django.db import models, transaction
from django.utils import timezone
from yandex_tracker_client import TrackerClient

from core.loggers import yt_logger
from core.utils import Config
from core.wraps import safe_request
from emails.models import EmailFolder, EmailMessage
from emails.utils import EmailManager
from incidents.constants import (
    DEFAULT_STATUS_DESC,
    DEFAULT_STATUS_NAME,
    MAX_EMAILS_ON_CLOSED_INCIDENTS,
)
from incidents.models import Incident, IncidentStatus, IncidentStatusHistory

from .constants import (
    MAX_ATTACHMENT_SIZE_IN_YT,
    SEND_AUTO_EMAIL_ON_CLOSED_INCIDENT,
    IsExpiredSLA,
    IsNewMsg,
)
from .exceptions import YandexTrackerAuthErr

yt_manager_config = {
    'YT_CLIENT_ID': os.getenv('YT_CLIENT_ID'),
    'YT_CLIENT_SECRET': os.getenv('YT_CLIENT_SECRET'),
    'YT_ACCESS_TOKEN': os.getenv('YT_ACCESS_TOKEN'),
    'YT_REFRESH_TOKEN': os.getenv('YT_REFRESH_TOKEN'),
    'YT_ORGANIZATION_ID': os.getenv('YT_ORGANIZATION_ID'),
    'YT_QUEUE': os.getenv('YT_QUEUE'),
    'YT_DATABASE_ID_GLOBAL_FIELD_ID': os.getenv('YT_DATABASE_ID_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_EMAILS_IDS_GLOBAL_FIELD_ID': os.getenv('YT_EMAILS_IDS_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_POLE_NUMBER_GLOBAL_FIELD_ID': os.getenv('YT_POLE_NUMBER_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_BASE_STATION_GLOBAL_FIELD_ID': os.getenv('YT_BASE_STATION_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_EMAIL_DATETIME_GLOBAL_FIELD_ID': os.getenv('YT_EMAIL_DATETIME_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_IS_NEW_MSG_GLOBAL_FIELD_ID': os.getenv('YT_IS_NEW_MSG_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_SLA_AVR_DEADLINE_GLOBAL_FIELD_ID': os.getenv('YT_SLA_AVR_DEADLINE_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_IS_SLA_AVR_EXPIRED_GLOBAL_FIELD_ID': os.getenv('YT_IS_SLA_AVR_EXPIRED_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_SLA_RVR_DEADLINE_GLOBAL_FIELD_ID': os.getenv('YT_SLA_RVR_DEADLINE_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_IS_SLA_RVR_EXPIRED_GLOBAL_FIELD_ID': os.getenv('YT_IS_SLA_RVR_EXPIRED_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_OPERATOR_NAME_GLOBAL_FIELD_NAME': os.getenv('YT_OPERATOR_NAME_GLOBAL_FIELD_NAME'),  # noqa: E501
    'YT_AVR_NAME_GLOBAL_FIELD_ID': os.getenv('YT_AVR_NAME_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_MONITORING_GLOBAL_FIELD_ID': os.getenv('YT_MONITORING_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID': os.getenv('YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID'),  # noqa: E501
    'YT_SUBTYPE_OF_INCIDENT_LOCAL_FIELD_ID': os.getenv('YT_SUBTYPE_OF_INCIDENT_LOCAL_FIELD_ID'),  # noqa: E501
    'YT_CATEGORY_LOCAL_FIELD_ID': os.getenv('YT_CATEGORY_LOCAL_FIELD_ID'),  # noqa: E501
    'YT_ON_GENERATION_STATUS_KEY': os.getenv('YT_ON_GENERATION_STATUS_KEY'),  # noqa: E501
    'YT_NOTIFY_OPERATOR_ISSUE_IN_WORK_STATUS_KEY': os.getenv('YT_NOTIFY_OPERATOR_ISSUE_IN_WORK_STATUS_KEY'),  # noqa: E501
    'YT_NOTIFIED_OPERATOR_ISSUE_IN_WORK_STATUS_KEY': os.getenv('YT_NOTIFIED_OPERATOR_ISSUE_IN_WORK_STATUS_KEY'),  # noqa: E501
    'YT_NOTIFY_OPERATOR_ISSUE_CLOSED_STATUS_KEY': os.getenv('YT_NOTIFY_OPERATOR_ISSUE_CLOSED_STATUS_KEY'),  # noqa: E501
    'YT_NOTIFIED_OPERATOR_ISSUE_CLOSED_STATUS_KEY': os.getenv('YT_NOTIFIED_OPERATOR_ISSUE_CLOSED_STATUS_KEY'),  # noqa: E501
    'YT_NOTIFY_CONTRACTOR_IN_WORK_STATUS_KEY': os.getenv('YT_NOTIFY_CONTRACTOR_IN_WORK_STATUS_KEY'),  # noqa: E501
    'YT_NOTIFIED_CONTRACTOR_IN_WORK_STATUS_KEY': os.getenv('YT_NOTIFIED_CONTRACTOR_IN_WORK_STATUS_KEY'),  # noqa: E501
    'YT_AVR_START_DATE_FIELD_ID': os.getenv('YT_AVR_START_DATE_FIELD_ID'),  # noqa: E501
    'YT_AVR_END_DATE_FIELD_ID': os.getenv('YT_AVR_END_DATE_FIELD_ID'),  # noqa: E501
    'YT_RVR_START_DATE_FIELD_ID': os.getenv('YT_RVR_START_DATE_FIELD_ID'),  # noqa: E501
    'YT_RVR_END_DATE_FIELD_ID': os.getenv('YT_RVR_END_DATE_FIELD_ID'),  # noqa: E501
    'YT_DGU_START_DATE_FIELD_ID': os.getenv('YT_DGU_START_DATE_FIELD_ID'),  # noqa: E501
    'YT_DGU_END_DATE_FIELD_ID': os.getenv('YT_DGU_END_DATE_FIELD_ID'),  # noqa: E501
}
Config.validate_env_variables(yt_manager_config)


class YandexTrackerManager:
    retries = 3
    timeout = 30
    cache_timer = 300

    current_user_url = 'https://api.tracker.yandex.net/v2/myself'
    token_url = 'https://oauth.yandex.ru/token'
    search_issues_url = (
        'https://api.tracker.yandex.net/v2/issues/_search?expand=transitions')
    all_users_url = 'https://api.tracker.yandex.net/v2/users'
    temporary_file_url = 'https://api.tracker.yandex.net/v2/attachments/'
    create_issue_url = 'https://api.tracker.yandex.net/v2/issues/'
    filter_issues_url = 'https://api.tracker.yandex.net/v2/issues/_search'
    statuses_url = 'https://api.tracker.yandex.net/v2/statuses'
    custom_field_url = 'https://api.tracker.yandex.net/v2/fields'
    all_field_categories_url = (
        'https://api.tracker.yandex.net/v3/fields/categories')

    closed_status_key = 'closed'
    error_status_key = 'error'
    in_work_status_key = 'inProgress'
    need_acceptance_status_key = 'needAcceptance'
    new_status_key = 'new'

    system_category_field_id = '000000000000000000000001'
    timestamp_category_field_id = '000000000000000000000002'
    agile_category_field_id = '000000000000000000000003'
    email_category_field_id = '000000000000000000000004'
    sla_category_field_id = '000000000000000000000005'

    def __init__(
        self,
        cliend_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        organisation_id: str,
        queue: str,
        database_global_field_id: str,
        emails_ids_global_field_id: str,
        pole_number_global_field_id: str,
        base_station_global_field_id: str,
        email_datetime_global_field_id: str,
        is_new_msg_global_field_id: str,
        sla_avr_deadline_global_field_id: str,
        is_sla_avr_expired_global_field_id: str,
        sla_rvr_deadline_global_field_id: str,
        is_sla_rvr_expired_global_field_id: str,
        avr_start_date_global_field_id: str,
        avr_end_date_global_field_id: str,
        rvr_start_date_global_field_id: str,
        rvr_end_date_global_field_id: str,
        dgu_start_date_global_field_id: str,
        dgu_end_date_global_field_id: str,
        operator_name_global_field_name: str,
        avr_name_global_field_id: str,
        monitoring_global_field_id: str,
        type_of_incident_local_field_id: str,
        subtype_of_incident_local_field_id: str,
        category_local_field_id: str,
        on_generation_status_key: str,
        notify_op_issue_in_work_status_key: str,
        notified_op_issue_in_work_status_key: str,
        notify_op_issue_closed_status_key: str,
        notified_op_issue_closed_status_key: str,
        notify_contractor_in_work_status_key: str,
        notified_contractor_in_work_status_key: str,
    ):
        self.client_id = cliend_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.queue = queue
        self.organisation_id = organisation_id

        self.database_global_field_id = database_global_field_id
        self.emails_ids_global_field_id = emails_ids_global_field_id
        self.pole_number_global_field_id = pole_number_global_field_id
        self.base_station_global_field_id = base_station_global_field_id
        self.email_datetime_global_field_id = email_datetime_global_field_id
        self.is_new_msg_global_field_id = is_new_msg_global_field_id
        self.operator_name_global_field_name = operator_name_global_field_name
        self.avr_name_global_field_id = avr_name_global_field_id
        self.monitoring_global_field_id = monitoring_global_field_id

        self.sla_avr_deadline_global_field_id = (
            sla_avr_deadline_global_field_id
        )
        self.is_sla_avr_expired_global_field_id = (
            is_sla_avr_expired_global_field_id
        )
        self.sla_rvr_deadline_global_field_id = (
            sla_rvr_deadline_global_field_id
        )
        self.is_sla_rvr_expired_global_field_id = (
            is_sla_rvr_expired_global_field_id
        )
        self.avr_start_date_global_field_id = avr_start_date_global_field_id
        self.avr_end_date_global_field_id = avr_end_date_global_field_id
        self.rvr_start_date_global_field_id = rvr_start_date_global_field_id
        self.rvr_end_date_global_field_id = rvr_end_date_global_field_id
        self.dgu_start_date_global_field_id = dgu_start_date_global_field_id
        self.dgu_end_date_global_field_id = dgu_end_date_global_field_id

        self.type_of_incident_local_field_id = type_of_incident_local_field_id
        self.subtype_of_incident_local_field_id = (
            subtype_of_incident_local_field_id
        )
        self.category_local_field_id = category_local_field_id

        self.notify_op_issue_in_work_status_key = (
            notify_op_issue_in_work_status_key
        )
        self.notified_op_issue_in_work_status_key = (
            notified_op_issue_in_work_status_key
        )
        self.notify_op_issue_closed_status_key = (
            notify_op_issue_closed_status_key
        )
        self.notified_op_issue_closed_status_key = (
            notified_op_issue_closed_status_key
        )
        self.notify_contractor_in_work_status_key = (
            notify_contractor_in_work_status_key
        )
        self.notified_contractor_in_work_status_key = (
            notified_contractor_in_work_status_key
        )

        self.on_generation_status_key = on_generation_status_key

        self._current_user_uid: Optional[str] = None
        self.local_fields_url = (
            f'https://api.tracker.yandex.net/v3/queues/{queue}/localFields')

        self.client = TrackerClient(
            token=self.access_token, org_id=self.organisation_id)

        self._statuses_cache = None
        self._statuses_last_update = 0

        self._users_cache = None
        self._users_last_update = 0

        self._real_users_cache = None
        self._real_users_last_update = 0

        self._local_fields_cache = None
        self._local_fields_last_update = 0

    def find_yt_number_in_text(self, text: str) -> Optional[str]:
        """Ищет первое вхождение: названия очереди, дефис и цифры"""
        match = re.search(rf'{self.queue}-\d+', text)
        return match.group(0) if match else None

    @property
    def headers(self):
        return {
            'Authorization': f'OAuth {self.access_token}',
            'X-Org-Id': self.organisation_id,
        }

    @property
    def check_token(self) -> bool:
        response = requests.get(self.current_user_url, headers=self.headers)
        return response.status_code == HTTPStatus.OK

    @staticmethod
    def emails_for_yandex_tracker(
        days: int = 1
    ) -> models.QuerySet[EmailMessage]:
        """
        Письма, которые должны быть добавлены в YandexTracker.

        Это письма, по которым был сформирован инцидент и они уже были
        добавлены в YandexTracker, или письма для которых сформирован инцидент.

        Исключаем письма старше N дней назад, чтобы не добавлять
        неактуальные инциденты при смене основного фильтра.

        Если у письма есть флаг need_2_add_in_yandex_tracker, то оно в любом
        случае попадает в выборку.

        Args:
            days (days): Количество дней назад, для фильтрации писем не
            зарегестрированных в YandexTracker. По умолчанию 1.
        Returns:
            Отсортированные от старых к новым QuerySet[EmailMessage] по
            email_incident_id, is_first_email, email_date, id.
        """
        incident_ids_in_yt = EmailMessage.objects.filter(
            was_added_2_yandex_tracker=True,
            email_incident__isnull=False,
        ).values('email_incident_id').distinct()

        emails_with_incidents_in_yt = EmailMessage.objects.filter(
            email_incident_id__in=models.Subquery(incident_ids_in_yt),
            is_email_from_yandex_tracker=False,
            was_added_2_yandex_tracker=False
        )

        emails_not_in_yt = EmailMessage.objects.filter(
            is_email_from_yandex_tracker=False,
            was_added_2_yandex_tracker=False,
            email_incident__isnull=False,
        )
        exclusion_date = timezone.now() - timedelta(days=days)

        # Union:
        emails = (
            emails_not_in_yt | emails_with_incidents_in_yt
        ).exclude(
            models.Q(email_date__lt=exclusion_date)
        )

        emails_need_2_add_in_yandex_tracker = EmailMessage.objects.filter(
            need_2_add_in_yandex_tracker=True,
            email_incident__isnull=False,
        )

        emails = emails | emails_need_2_add_in_yandex_tracker

        emails = emails.distinct().order_by(
            'email_incident_id', 'email_date', '-is_first_email', 'id'
        )

        return emails

    @staticmethod
    def get_sla_avr_status(incident: Optional[Incident]) -> str:
        """Определяет статус SLA АВР."""
        if not incident or not incident.sla_avr_deadline:
            return IsExpiredSLA.unknown

        if incident.avr_end_date:
            if incident.avr_end_date <= incident.sla_avr_deadline:
                return IsExpiredSLA.not_expired
            else:
                return IsExpiredSLA.is_expired

        if timezone.now() > incident.sla_avr_deadline:
            return IsExpiredSLA.is_expired

        time_remaining = incident.sla_avr_deadline - timezone.now()
        if time_remaining <= timedelta(hours=1):
            return IsExpiredSLA.one_hour

        return IsExpiredSLA.in_work

    @staticmethod
    def get_sla_rvr_status(incident: Optional[Incident]) -> str:
        """Определяет статус SLA РВР."""
        if not incident or not incident.sla_rvr_deadline:
            return IsExpiredSLA.unknown

        if incident.rvr_end_date:
            if incident.rvr_end_date <= incident.sla_rvr_deadline:
                return IsExpiredSLA.not_expired
            else:
                return IsExpiredSLA.is_expired

        if timezone.now() > incident.sla_rvr_deadline:
            return IsExpiredSLA.is_expired

        time_remaining = incident.sla_rvr_deadline - timezone.now()
        if time_remaining <= timedelta(hours=1):
            return IsExpiredSLA.one_hour

        return IsExpiredSLA.in_work

    @safe_request(yt_logger, retries=retries, timeout=timeout)
    def _make_request(
        self, method: HTTPMethod, url: str, **kwargs
    ) -> dict:
        """
        Универсальный метод для выполнения HTTP-запросов.

        Args:
            method (str): HTTP метод ('GET', 'POST', 'PUT', 'DELETE')
            url (str): Полный URL
            kwargs: параметры для requests (json, data, params, files, etc.)

        Особенности:
            Если передать в качестве kwarg sub_func_name, это имя будет
            использовано для логирования метода класса.
        """
        response = requests.request(
            method.value, url, headers=self.headers, **kwargs
        )
        kwargs.pop('sub_func_name', None)

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            yt_logger.info('Токен устарел, обновляем.')
            self._refresh_access_token()
            return requests.request(
                method.value, url, headers=self.headers, **kwargs)

        return response

    def _refresh_access_token(self):
        """Обновляет access_token и refresh_token."""
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
        }
        response = requests.post(self.token_url, data=data)
        tokens = response.json()
        try:
            self.access_token = tokens['access_token']
            self.refresh_token = tokens['refresh_token']
            self.client = TrackerClient(
                token=self.access_token, org_id=self.organisation_id)
        except KeyError:
            raise YandexTrackerAuthErr(response.status_code, response.text)

    @property
    def current_user_uid(self) -> str:
        """Получаем UID текущего пользователя."""
        if not self._current_user_uid:
            self._current_user_uid = str(self.current_user_info['uid'])
        return self._current_user_uid

    @property
    def current_user_info(self) -> dict:
        """Возвращает информацию о текущем пользователе в Яндекс.Трекере."""
        return self._make_request(
            HTTPMethod.GET,
            self.current_user_url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    @property
    def real_users_in_yt_tracker(self) -> dict[str, int]:
        """
        Список реальных пользователей в Yandex Tracker.

        Особенности:
            Логины пользователей должны быть такими же, как в Django
        Users, иначе на этого пользователя невозможно будет назначить задачу.
        """
        if (
            self._real_users_cache is None
            or time.time() - self._real_users_last_update > self.cache_timer
        ):
            users = self.users_info
            self._real_users_cache = {
                user['login']: user['uid'] for user in users
                if not user['disableNotifications']
            }
            self._real_users_last_update = time.time()
        return self._real_users_cache

    @property
    def users_info(self) -> list[dict]:
        """Список всех пользователей с кэшированием."""
        if (
            self._users_cache is None
            or time.time() - self._users_last_update > self.cache_timer
        ):
            self._users_cache = self._get_users_info()
            self._users_last_update = time.time()
        return self._users_cache

    def _get_users_info(self):
        return self._make_request(
            HTTPMethod.GET,
            self.all_users_url,
            sub_func_name=inspect.currentframe().f_code.co_name
        )

    @property
    def all_statuses(self) -> list[dict]:
        """Получение всех статусов с кэшированием."""
        if (
            self._statuses_cache is None
            or time.time() - self._statuses_last_update > self.cache_timer
        ):
            self._statuses_cache = self._get_all_statuses()
            self._statuses_last_update = time.time()
        return self._statuses_cache

    def _get_all_statuses(self):
        return self._make_request(
            HTTPMethod.GET,
            self.statuses_url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def select_issue(
        self, database_id: Optional[int] = None, key: Optional[str] = None
    ) -> list[dict]:
        """Поиск задачи по глобальному полю database_id или по её ключу key."""

        if database_id is None and key is None:
            raise ValueError(
                'Необходимо указать номер задачи из БД или ключ задачи.'
            )
        filter = {'queue': self.queue}

        if database_id is not None:
            filter[self.database_global_field_id] = database_id

        if key is not None:
            filter['key'] = key

        payload = {'filter': filter}

        return self._make_request(
            HTTPMethod.POST,
            self.search_issues_url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def create_comment(
        self,
        issue_key: str,
        comment: str,
        temp_files: Optional[list[str]] = None,
    ) -> dict:
        payload = {'text': comment}

        if temp_files:
            payload['attachmentIds'] = temp_files

        url = f'{self.create_issue_url}{issue_key}/comments'
        return self._make_request(
            HTTPMethod.POST,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def is_comment_related(
        self, comment: dict, email: EmailMessage
    ) -> bool:
        comment_text: str = comment.get('text', '')
        comment_text_meta = comment_text.split('```text')[0]

        if not comment_text_meta:
            return False

        comment_created_by: str = comment['createdBy']['id']

        if self.current_user_uid != comment_created_by:
            return False

        # Если указан ID сразу возвращаем True
        m = re.search(r'\*\*ID:\*\*\s*\|\s*`([^`]+)`', comment_text_meta)
        email_id = m.group(1).strip() if m else None
        if email_id is not None and email_id == str(email.id):
            return True

        m = re.search(r'###.*?"\*\*(.*?)\*\*"', comment_text_meta)
        subject = m.group(1).strip() if m else None
        if not subject or subject != email.email_subject:
            return False

        m = re.search(r'\*\*От:\*\*\s*\|\s*`([^`]+)`', comment_text_meta)
        email_from = m.group(1).strip() if m else None
        if not email_from or email_from != email.email_from:
            return False

        m = re.search(r'\*\*Дата:\*\*\s*\|\s*`([^`]+)`', comment_text_meta)
        date_raw = m.group(1).strip() if m else None

        email_date_moscow = email.email_date.astimezone(
            timezone.get_current_timezone()
        )
        email_formatted_date = email_date_moscow.strftime('%d.%m.%Y %H:%M')

        if not date_raw or date_raw != email_formatted_date:
            return False

        return True

    def delete_comment(self, issue_key: str, comment_id: int) -> dict:
        url = f'{self.create_issue_url}{issue_key}/comments/{comment_id}'
        return self._make_request(
            HTTPMethod.DELETE,
            url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def create_comment_like_email_and_send(
        self,
        email_from: str,
        issue_key: str,
        subject: Optional[str],
        text: Optional[str],
        to: list[str],
        cc: Optional[list[str]] = None,
        temp_files: Optional[list[str]] = None
    ) -> dict:
        """Создаем комментарий-email и отправляем его из YandexTracker."""
        to = set([em for em in to if em != email_from])
        cc = set([em for em in cc if em not in to]) if cc else set()

        payload = {
            'email': {
                'subject': subject,
                'text': text,
                'info': {
                    'from': email_from,
                    'to': list(to),
                    'cc': list(cc)
                },
            }
        }

        if temp_files:
            payload['attachmentIds'] = temp_files

        url = f'{self.create_issue_url}{issue_key}/comments'
        return self._make_request(
            HTTPMethod.POST,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def download_temporary_file(self, filepath: str) -> dict:
        with open(filepath, 'rb') as file:
            filename = os.path.basename(filepath)
            files = {'file': (filename, file)}
            return self._make_request(
                HTTPMethod.POST,
                self.temporary_file_url,
                files=files,
                sub_func_name=inspect.currentframe().f_code.co_name,
            )

    def download_email_temp_files(self, email: EmailMessage) -> list[str]:
        """Возвращает ID загруженных в YandexTracker временных файлов."""
        temp_files = []

        for filepath in EmailManager.get_email_attachments(email):
            if not filepath or not os.path.isfile(filepath):
                continue

            size = os.path.getsize(filepath)
            if size > MAX_ATTACHMENT_SIZE_IN_YT:
                yt_logger.warning(
                    f'Превышен лимит размера файла: {filepath} '
                    f'({size} байт > допустимых '
                    f'{MAX_ATTACHMENT_SIZE_IN_YT} байт). '
                    'Файл пропущен.'
                )
                continue

            response = self.download_temporary_file(filepath)
            file_id = response.get('id')

            if file_id:
                temp_files.append(file_id)
            else:
                yt_logger.error(
                    f'Не удалось загрузить временный файл {filepath}.'
                    f'Ошибка: {response}'
                )

        return temp_files

    def create_or_update_issue(
        self,
        key: Optional[str],
        summary: str,
        database_id: int,
        pole_number: Optional[str],
        base_station_number: Optional[str],
        description: Optional[str],
        assignee: Optional[str],
        email_datetime: Optional[datetime],
        email_from: Optional[str],
        email_to: Optional[list[str]],
        email_cc: Optional[list[str]],
        temp_files: Optional[list[str]],
        issue_type: str = 'incident',
        author: str = 'yndx-tracker-cnt-robot',
    ) -> dict:
        """
        Создание или обновление инцидента в YandexTracker.

        Если ключ задачи (key) отсутствует, тогда создаем новую задачу.
        В противном случае обновляем.
        """
        email_datetime = email_datetime.isoformat() if isinstance(
            email_datetime, datetime
        ) else None

        payload = {
            'summary': summary,
            self.database_global_field_id: database_id,
            self.pole_number_global_field_id: pole_number,
            self.base_station_global_field_id: base_station_number,
            'description': description,
            self.email_datetime_global_field_id: email_datetime,
            'emailFrom': email_from,
            'emailTo': email_to,
            'emailCc': email_cc,
            self.is_new_msg_global_field_id: IsNewMsg.yes,
        }

        add_payload = {
            'queue': self.queue,
            'type': issue_type,
            'author': author,
            'assignee': assignee,
            self.is_sla_avr_expired_global_field_id: (
                self.get_sla_avr_status(None)
            ),
        } if not key else {}

        payload.update(add_payload)

        if temp_files:
            payload['attachmentIds'] = temp_files

        url = f'{self.create_issue_url}{key}' if key else self.create_issue_url

        if not key:
            return self._make_request(
                HTTPMethod.POST,
                url,
                json=payload,
                sub_func_name=inspect.currentframe().f_code.co_name,
            )

        return self._make_request(
            HTTPMethod.PATCH,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def update_issue_sla_status(self, issue: dict, incident: Incident) -> dict:
        """Обновление статусов SLA"""
        key = issue['key']
        payload = {
            self.is_sla_avr_expired_global_field_id: (
                self.get_sla_avr_status(incident)
            ),
            self.is_sla_rvr_expired_global_field_id: (
                self.get_sla_rvr_status(incident)
            )
        }
        url = f'{self.create_issue_url}{key}'
        return self._make_request(
            HTTPMethod.PATCH,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def select_issue_comments(self, issue_key: str) -> list[dict]:
        url = f'{self.create_issue_url}{issue_key}/comments'
        return self._make_request(
            HTTPMethod.GET,
            url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def _comment_like_email_with_markdown(self, email: EmailMessage) -> str:
        email_to = [eml.email_to for eml in email.email_msg_to.all()]
        email_cc = [eml.email_to for eml in email.email_msg_cc.all()]

        # Будем использовать временную зону указанную в настройках Django:
        email_date_moscow = email.email_date.astimezone(
            timezone.get_current_timezone())
        formatted_date = email_date_moscow.strftime('%d.%m.%Y %H:%M')

        # Форматируем тему письма:
        subject = ''
        if email.email_subject:
            subject = EmailManager.normalize_text_with_json(
                email.email_subject, True)
            subject = subject.replace('```', '')

        comment_like_email = [
            f'### 📧 "**{subject}**"' if subject else '*Без темы*',
            '',
            '| | |',
            '|-|-|',
            f'| **От:** | `{email.email_from}` |',
        ]

        if email_to:
            comment_like_email.append(
                f'| **Кому:** | `{', '.join(email_to)}` |')

        if email_cc:
            comment_like_email.append(
                f'| **Копия:** | `{', '.join(email_cc)}` |')

        comment_like_email.extend([
            f'| **Дата:** | `{formatted_date}` |',
            f'| **ID:** | `{email.id}` |',
            '',
            '```text',  # Тип контента для подсветки (text, email, markdown)
        ])

        # Обрабатываем тело письма:
        if email.email_body:
            normalized_body = EmailManager.normalize_text_with_json(
                email.email_body, True)

            # Улучшаем форматирование тела письма
            # Убираем лишние переносы строк и добавляем Markdown-форматирование
            # Два пробела для переноса строк в Markdown:
            formatted_body = normalized_body.replace('\n', '  \n')
            formatted_body = formatted_body.replace('```', '')

            # Если есть цитаты (обычно начинаются с ">"), форматируем их как
            # blockquote:
            if '>' in formatted_body:
                lines = formatted_body.split('\n')
                formatted_lines = []
                in_quote = False

                for line in lines:
                    if line.strip().startswith('>'):
                        if not in_quote:
                            # Пустая строка перед цитатой:
                            formatted_lines.append('')
                        formatted_lines.append('> ' + line.lstrip('> '))
                        in_quote = True
                    else:
                        if in_quote:
                            # Пустая строка после цитаты:
                            formatted_lines.append('')
                        formatted_lines.append(line)
                        in_quote = False

                formatted_body = '\n'.join(formatted_lines)

            comment_like_email.append(formatted_body)
        else:
            comment_like_email.append('*Тело письма отсутствует*')

        comment_like_email.extend([
            '```',
        ])

        return '\n'.join(comment_like_email)

    def add_issue_email_comment(self, email: EmailMessage, issue: dict):
        """Создаёт комментарий по email, которого ещё нет в YandexTracker."""
        issue_key: str = issue['key']

        emails_ids_str: str = issue.get(self.emails_ids_global_field_id, '')
        existing_email_ids = set()
        for value in emails_ids_str.split(','):
            value = value.strip()
            if value:
                try:
                    existing_email_ids.add(int(value))
                except ValueError:
                    pass

        if (
            email.pk in existing_email_ids
            and not email.need_2_add_in_yandex_tracker
        ):
            return

        temp_files = self.download_email_temp_files(email)
        comment_text = self._comment_like_email_with_markdown(email)
        self.create_comment(issue_key, comment_text, temp_files)

        updated_email_ids = EmailMessage.objects.filter(
            email_incident=email.email_incident,
            was_added_2_yandex_tracker=True
        ).values_list('id', flat=True).distinct().order_by('id')

        updated_email_ids = list(updated_email_ids)
        if email.pk not in updated_email_ids:
            updated_email_ids.append(email.pk)

        updated_email_ids.sort()
        updated_email_ids_str = ', '.join(str(pk) for pk in updated_email_ids)

        # Не забываем, что вместе с сообщением может прийти уточнение по
        # шифру опоры и номеру БС:
        payload = {
            self.emails_ids_global_field_id: updated_email_ids_str,
            self.is_new_msg_global_field_id: IsNewMsg.yes,
        }

        url = f'{self.create_issue_url}{issue_key}'

        return self._make_request(
            HTTPMethod.PATCH,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def _prepare_data_from_email(self, email_incident: EmailMessage) -> dict:
        """Подготовка данных для отправки в YandexTracker."""
        incident: Incident = email_incident.email_incident
        database_id: int = incident.pk

        summary = EmailManager.normalize_text_with_json(
            email_incident.email_subject, True
        ) if email_incident.email_subject else f'Инцидент №{database_id}'

        description = EmailManager.normalize_text_with_json(
            email_incident.email_body, True
        ) if email_incident.email_body else None

        pole_number = incident.pole.pole if incident.pole else None
        base_station_number = (
            incident.base_station.bs_name if incident.base_station else None
        )

        username = (
            incident.responsible_user.username
        ) if incident.responsible_user else None

        assignee = username if username and username in (
            self.real_users_in_yt_tracker.keys()
        ) else None

        email_datetime = email_incident.email_date
        email_from = email_incident.email_from
        email_to = [
            eml.email_to for eml in email_incident.email_msg_to.all()
        ]
        email_cc = [
            eml.email_to for eml in email_incident.email_msg_cc.all()
        ]
        issues = self.select_issue(database_id)

        if not issues and incident.code:
            issues = self.select_issue(key=incident.code)

        key = issues[0]['key'] if issues else None

        return {
            'database_id': database_id,
            'summary': summary,
            'description': description,
            'pole_number': pole_number,
            'base_station_number': base_station_number,
            'assignee': assignee,
            'email_datetime': email_datetime,
            'email_from': email_from,
            'email_to': email_to,
            'email_cc': email_cc,
            'issues': issues,
            'key': key,
        }

    def _check_yt_issue(self, issue: dict, email_incident: EmailMessage):
        incident = email_incident.email_incident
        update_incident = False

        comment_for_again_open = (
            'Инцидент автоматически открыт повторно: получено '
            f'{MAX_EMAILS_ON_CLOSED_INCIDENTS}-е письмо после его закрытия.'
        )

        if not incident.code or incident.code != issue['key']:
            incident.code = issue['key']
            update_incident = True

        # Открываем закрытый инцидент, если пришло более N сообщений:
        if EmailManager.is_nth_email_after_incident_close(
            incident, MAX_EMAILS_ON_CLOSED_INCIDENTS
        ):
            incident.is_incident_finish = False

            update_incident = True

            self.update_issue_status(
                issue['key'],
                self.in_work_status_key,
                comment_for_again_open,
            )

        if update_incident:
            incident.save()

        # Отправка автоответа, если оператор пишет в уже закрытую заявку:
        if (
            SEND_AUTO_EMAIL_ON_CLOSED_INCIDENT
            and incident.is_incident_finish
            and email_incident.folder == EmailFolder.get_inbox()
        ):
            from emails.email_parser import email_parser  # noqa: I001

            from .auto_emails import AutoEmailsFromYT  # noqa: I003

            auto_email = AutoEmailsFromYT(self, email_parser, issue, incident)
            auto_email.auto_reply_incident_is_closed(email_incident)

        # Если по письму пришло уточнение по шифру опоры или номеру БС,
        # добавляем в трекер:
        db_pole_number = incident.pole.pole if incident.pole else None
        db_base_station_number = (
            incident.base_station.bs_name if incident.base_station else None
        )
        yt_pole_number = issue.get(self.pole_number_global_field_id)
        yt_base_station_number = issue.get(self.base_station_global_field_id)

        if (
            (not yt_pole_number and db_pole_number)
            or (not yt_base_station_number and db_base_station_number)
        ):
            pole_number = yt_pole_number or db_pole_number
            base_station_number = (
                yt_base_station_number or db_base_station_number
            )

            issue_key = issue['key']

            payload = {
                self.pole_number_global_field_id: pole_number,
                self.base_station_global_field_id: base_station_number,
            }

            url = f'{self.create_issue_url}{issue_key}'
            self._make_request(
                HTTPMethod.PATCH,
                url,
                json=payload,
                sub_func_name=inspect.currentframe().f_code.co_name,
            )

    def add_incident_to_yandex_tracker(
        self,
        email_incident: EmailMessage,
        is_first_email: bool,
    ):
        """
        Создание инцидента в YandexTracker.

        Особенности:
            У EmailMessage обязательно должен быть Incident.
        """
        data_for_yt = self._prepare_data_from_email(email_incident)

        # Задача будет даже если создана вручную:
        issues: list[dict] = data_for_yt['issues']
        key = issues[0]['key'] if issues else None

        # Инцидент только пришел и ещё отсутствует в YandexTracker:
        if not issues and is_first_email:
            temp_files = self.download_email_temp_files(email_incident)

            issue = self.create_or_update_issue(
                key=key,
                summary=data_for_yt['summary'],
                database_id=data_for_yt['database_id'],
                pole_number=data_for_yt['pole_number'],
                base_station_number=data_for_yt['base_station_number'],
                description=data_for_yt['description'],
                assignee=data_for_yt['assignee'],
                email_datetime=data_for_yt['email_datetime'],
                email_from=data_for_yt['email_from'],
                email_to=data_for_yt['email_to'],
                email_cc=data_for_yt['email_cc'],
                temp_files=temp_files,
            )

            self._check_yt_issue(issue, email_incident)

        # Инцидент отсутствует в YandexTracker, но по нему пришло уточнение,
        # поэтому надо восстановить полностью цепочку писем для инцидента:
        elif not issues and not is_first_email:
            all_email_incident = EmailMessage.objects.filter(
                email_incident=email_incident.email_incident
            ).order_by('email_date', '-is_first_email', 'id')

            first_email_incident = all_email_incident.first()
            new_data_for_yt = self._prepare_data_from_email(
                first_email_incident)
            temp_files = self.download_email_temp_files(first_email_incident)

            issue = self.create_or_update_issue(
                key=key,
                summary=new_data_for_yt['summary'],
                database_id=new_data_for_yt['database_id'],
                pole_number=new_data_for_yt['pole_number'],
                base_station_number=new_data_for_yt['base_station_number'],
                description=new_data_for_yt['description'],
                assignee=new_data_for_yt['assignee'],
                email_datetime=new_data_for_yt['email_datetime'],
                email_from=new_data_for_yt['email_from'],
                email_to=new_data_for_yt['email_to'],
                email_cc=new_data_for_yt['email_cc'],
                temp_files=temp_files,
            )

            self._check_yt_issue(issue, email_incident)

            for email in all_email_incident[1:]:
                self.add_issue_email_comment(email, issue)

        # Инцидент уже зарегестрирован в YandexTracker:
        else:
            for issue in issues:
                pole_number = issue.get(
                    self.pole_number_global_field_id,
                    data_for_yt['pole_number']
                )
                base_station_number = issue.get(
                    self.base_station_global_field_id,
                    data_for_yt['base_station_number']
                )
                key: str = issue['key']

                # Повторная обработка первого письма:
                if (
                    is_first_email
                    and email_incident.email_incident.is_auto_incident
                ):
                    temp_files = self.download_email_temp_files(email_incident)

                    issue = self.create_or_update_issue(
                        key=key,
                        summary=data_for_yt['summary'],
                        database_id=data_for_yt['database_id'],
                        pole_number=pole_number,
                        base_station_number=base_station_number,
                        description=data_for_yt['description'],
                        assignee=data_for_yt['assignee'],
                        email_datetime=data_for_yt['email_datetime'],
                        email_from=data_for_yt['email_from'],
                        email_to=data_for_yt['email_to'],
                        email_cc=data_for_yt['email_cc'],
                        temp_files=temp_files,
                    )

                # Необходимо добавить новые сообщения ввиде комментаривев:
                else:
                    self.add_issue_email_comment(email_incident, issue)

                self._check_yt_issue(issue, email_incident)

    def filter_issues(
        self, yt_filter: dict, days_ago: int = 7, chunk_days: int = 5
    ) -> Generator[list[dict], None, None]:
        """
        Фильтрует задачи по переданному фильтру и диапазону дат, учитывая лимит
        в 10_000 элементов.
        Разбивает диапазон дат на куски по chunk_days, чтобы обойти ограничение
        API.
        """
        per_page = 1000   # максимум по документации
        max_pages = 10    # 10 × 1000 = 10_000 элементов

        now: datetime = timezone.now()
        start_date: datetime = now - timedelta(days=days_ago)

        yt_filter['queue'] = self.queue

        for chunk_start, chunk_end in self.split_date_range(
            start_date, now, chunk_days
        ):
            page = 1

            yt_filter['updatedAt'] = {
                'from': chunk_start.isoformat(),
                'to': chunk_end.isoformat(),
            }

            payload = {'filter': yt_filter, 'order': '-updatedAt'}

            while page <= max_pages:
                params = {
                    'page': page,
                    'perPage': per_page,
                }

                if page > 1:
                    time.sleep(1)  # чтобы не заддосить API

                batch = self._make_request(
                    HTTPMethod.POST,
                    self.filter_issues_url,
                    json=payload,
                    params=params,
                    sub_func_name=inspect.currentframe().f_code.co_name,
                )

                if not batch:
                    break

                yield batch

                if len(batch) < per_page:
                    break

                page += 1

    @staticmethod
    def split_date_range(
        start: datetime,
        end: datetime,
        chunk_days: int,
        newest_first: bool = True
    ) -> Generator[tuple[datetime, datetime], None, None]:
        """
        Разбивает диапазон дат на интервалы по chunk_days.

        Args:
            start (datetime): начало диапазона
            end (datetime): конец диапазона
            chunk_days (int): размер одного интервала в днях
            newest_first (bool): если True — сначала возвращаются самые новые
                интервалы (от end к start), если False — от старых к новым (от
                start к end).
                По умолчанию `True`.
        """
        if newest_first:
            current_end = end
            while current_end > start:
                current_start = max(
                    current_end - timedelta(days=chunk_days), start
                )
                yield current_start, current_end
                current_end = current_start
        else:
            current_start = start
            while current_start < end:
                current_end = min(
                    current_start + timedelta(days=chunk_days), end
                )
                yield current_start, current_end
                current_start = current_end

    def closed_issues(
        self, days_ago: int = 7
    ) -> Generator[list[dict], None, None]:
        closed_statuses: list[str] = [
            {'id': status['id']}
            for status in self.all_statuses
            if status['key'] in (
                self.closed_status_key, self.on_generation_status_key
            )
        ]
        yield from self.filter_issues({'status': closed_statuses}, days_ago)

    def unclosed_issues(
        self, days_ago: int = 7
    ) -> Generator[list[dict], None, None]:
        unclosed_statuses: list[str] = [
            {'id': status['id']}
            for status in self.all_statuses
            if status['key'] not in (
                self.closed_status_key, self.on_generation_status_key
            )
        ]
        yield from self.filter_issues({'status': unclosed_statuses}, days_ago)

    @property
    def all_local_fields(self) -> list[dict]:
        """Кэширование локальных полей очереди."""
        if (
            self._local_fields_cache is None
            or time.time() - self._local_fields_last_update > self.cache_timer
        ):
            self._local_fields_cache = self._get_local_fields()
            self._local_fields_last_update = time.time()
        return self._local_fields_cache

    def _get_local_fields(self):
        return self._make_request(
            HTTPMethod.GET,
            self.local_fields_url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def get_available_transitions(self, issue_key: str) -> list[dict]:
        """
        Получить все доступные переходы в другие статусы для задачи.

        Лучше не кэшировать результаты этой функции.
        """
        url = (
            f'https://api.tracker.yandex.net/v3/issues/{issue_key}/transitions'
        )
        return self._make_request(
            HTTPMethod.GET,
            url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def select_local_field(
        self, local_field_id: str
    ) -> Optional[dict]:
        return next((
            field for field in self.all_local_fields
            if field['id'].endswith(local_field_id)
        ), None)

    def update_incident_data(
        self,
        issue: dict,
        type_of_incident_field: dict,
        type_of_incident: Optional[str],
        subtype_of_incident_field: dict,
        subtype_of_incident: Optional[str],
        category_field: dict,
        category: Optional[list[str]],
        email_datetime: Optional[datetime],
        sla_avr_deadline: Optional[datetime],
        is_sla_avr_expired: Optional[str],
        sla_rvr_deadline: Optional[datetime],
        is_sla_rvr_expired: Optional[str],
        avr_start_date: Optional[datetime],
        avr_end_date: Optional[datetime],
        rvr_start_date: Optional[datetime],
        rvr_end_date: Optional[datetime],
        dgu_start_date: Optional[datetime],
        dgu_end_date: Optional[datetime],
        pole_number: Optional[str],
        base_station_number: Optional[str],
        avr_name: Optional[str],
        operator_name: Optional[str],
        monitoring_data: Optional[str],
    ) -> dict:
        issue_key = issue['key']

        type_of_incident_field_key = type_of_incident_field['id']
        subtype_of_incident_field_key = subtype_of_incident_field['id']
        category_filed_key = category_field['id']

        email_datetime = email_datetime.isoformat() if isinstance(
            email_datetime, datetime) else None
        sla_avr_deadline = sla_avr_deadline.isoformat() if isinstance(
            sla_avr_deadline, datetime) else None
        sla_rvr_deadline = sla_rvr_deadline.isoformat() if isinstance(
            sla_rvr_deadline, datetime) else None

        avr_start_date = avr_start_date.isoformat() if isinstance(
            avr_start_date, datetime) else None
        avr_end_date = avr_end_date.isoformat() if isinstance(
            avr_end_date, datetime) else None
        rvr_start_date = rvr_start_date.isoformat() if isinstance(
            rvr_start_date, datetime) else None
        rvr_end_date = rvr_end_date.isoformat() if isinstance(
            rvr_end_date, datetime) else None
        dgu_start_date = dgu_start_date.isoformat() if isinstance(
            dgu_start_date, datetime) else None
        dgu_end_date = dgu_end_date.isoformat() if isinstance(
            dgu_end_date, datetime) else None

        payload = {
            type_of_incident_field_key: type_of_incident,
            subtype_of_incident_field_key: subtype_of_incident,
            category_filed_key: category,
            self.sla_avr_deadline_global_field_id: sla_avr_deadline,
            self.is_sla_avr_expired_global_field_id: is_sla_avr_expired,
            self.sla_rvr_deadline_global_field_id: sla_rvr_deadline,
            self.is_sla_rvr_expired_global_field_id: is_sla_rvr_expired,
            self.avr_start_date_global_field_id: avr_start_date,
            self.avr_end_date_global_field_id: avr_end_date,
            self.rvr_start_date_global_field_id: rvr_start_date,
            self.rvr_end_date_global_field_id: rvr_end_date,
            self.dgu_start_date_global_field_id: dgu_start_date,
            self.dgu_end_date_global_field_id: dgu_end_date,
            self.email_datetime_global_field_id: email_datetime,
            self.pole_number_global_field_id: pole_number,
            self.base_station_global_field_id: base_station_number,
            self.avr_name_global_field_id: avr_name,
            self.operator_name_global_field_name: operator_name,
            self.monitoring_global_field_id: monitoring_data,
        }

        url = f'{self.create_issue_url}{issue_key}'
        return self._make_request(
            HTTPMethod.PATCH,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def update_issue_status(
        self,
        issue_key: str,
        new_status_key: str,
        comment: str = '',
    ) -> Optional[dict]:
        """Выставление нового статуса задаче, согласно рабочему процессу."""
        transitions = self.get_available_transitions(issue_key)

        target_transition = next(
            (t for t in transitions if t['to']['key'] == new_status_key),
            None
        )

        if not target_transition:
            yt_logger.warning(
                f'Для {issue_key} не возможен переход в статус '
                f'{new_status_key}'
            )
            return

        url = (
            f'https://api.tracker.yandex.net/v3/issues/{issue_key}/'
            f'transitions/{target_transition['id']}/_execute'
        )
        payload = {'comment': comment}
        return self._make_request(
            HTTPMethod.POST,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def select_custom_field(self, field_id: str) -> dict:
        """Информации о кастомных полях кэширование использовать нельзя."""
        url = f'{self.custom_field_url}/{field_id}'
        return self._make_request(
            HTTPMethod.GET,
            url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def update_custom_field(
        self,
        field_id: str,
        readonly: bool,
        hidden: bool,
        visible: bool,
        name_en: Optional[str] = None,
        name_ru: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[str] = None,
        wait_if_busy: bool = True,
        timeout: int = 30,
    ) -> dict:
        """
        Обновляет пользовательское поле в Яндекс.Трекере.
        Параметры, равные None, в payload не добавляются.

        Args:
            field_id (str): Идентификатор пользовательского поля.
            name_en (str): Название поля на английском.
            name_ru (str): Название поля на русском.
            description (str): Описание поля.
            readonly (bool): Возможность редактировать значение поля.
            hidden (bool): Скрывает поле от пользователей в UI и API.
            visible (bool): Определяет, будет ли поле отображаться в UI
            (не в API).
            category_id (str): Идентификатор категории, к которой относится
            поле.


        Raises:
            KeyError: Если не верно указан category_id.

        Особенности:
            При попытки сделать readonly=True, которое бллокирует
            редактирование метод ждет пока предыдущее состояние закончится.

        """
        tmp_dir = tempfile.gettempdir()
        lock_file = os.path.join(tmp_dir, f'yt_field_{field_id}.lock')

        start_time = time.time()
        if wait_if_busy:
            while os.path.exists(lock_file):
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(
                        f'Поле {field_id} занято более {timeout} секунд'
                    )
                yt_logger.debug(
                    f'Поле {field_id} занято, lock {elapsed:.1f}s'
                )
                time.sleep(0.5)

        try:
            with open(lock_file, 'w') as f:
                f.write(str(time.time()))

            field_info = self.select_custom_field(field_id)
            version: int = field_info['version']
            url = f'{self.custom_field_url}/{field_id}?version={version}'

            valid_categories = {
                'system': self.system_category_field_id,
                'timestamp': self.timestamp_category_field_id,
                'agile': self.agile_category_field_id,
                'email': self.email_category_field_id,
                'sla': self.sla_category_field_id,
            }

            if category_id and category_id not in valid_categories.values():
                raise KeyError(
                    'Укажите один из доступных вариантов id: '
                    f'{valid_categories}'
                )

            payload = {}

            name_payload = {}
            if name_en is not None:
                name_payload['en'] = name_en
            if name_ru is not None:
                name_payload['ru'] = name_ru
            if name_payload:
                payload['name'] = name_payload

            if description is not None:
                payload['description'] = description

            payload['readonly'] = readonly
            payload['hidden'] = hidden
            payload['visible'] = visible

            return self._make_request(
                HTTPMethod.PATCH,
                url,
                json=payload,
                sub_func_name=inspect.currentframe().f_code.co_name,
            )

        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                yt_logger.debug(f'Lock для поля {field_id} снят')

    @property
    def field_categories(self):
        return self._make_request(
            HTTPMethod.GET,
            self.all_field_categories_url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    @transaction.atomic
    def create_incident_from_issue(
        self, issue: dict, is_incident_finish: bool
    ) -> Incident:
        """Создаем инцидент по задаче, созданной вручную в YandexTracker."""
        incident_date = issue['createdAt']
        incident = Incident.objects.create(
            incident_date=incident_date,
            is_incident_finish=is_incident_finish,
            is_auto_incident=False
        )

        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_STATUS_NAME,
            defaults={'description': DEFAULT_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments='Заявка была заведена через YandexTracker'
        )
        incident.statuses.add(status)

        issue_key: str = issue['key']

        payload = {
            self.database_global_field_id: incident.pk,
        }

        url = f'{self.create_issue_url}{issue_key}'

        # Лучше потом не возвращать, т.к. в этот момент поле где-то может
        # обновляться:
        self.update_custom_field(
            field_id=yt_manager.database_global_field_id,
            readonly=False,
            hidden=False,
            visible=False,
        )

        incident.code = issue_key
        incident.save()

        self._make_request(
            HTTPMethod.PATCH,
            url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

        return incident


yt_manager = YandexTrackerManager(
    cliend_id=yt_manager_config['YT_CLIENT_ID'],
    client_secret=yt_manager_config['YT_CLIENT_SECRET'],
    access_token=yt_manager_config['YT_ACCESS_TOKEN'],
    refresh_token=yt_manager_config['YT_REFRESH_TOKEN'],
    organisation_id=yt_manager_config['YT_ORGANIZATION_ID'],
    queue=yt_manager_config['YT_QUEUE'],
    database_global_field_id=yt_manager_config['YT_DATABASE_ID_GLOBAL_FIELD_ID'],  # noqa: E501
    emails_ids_global_field_id=yt_manager_config['YT_EMAILS_IDS_GLOBAL_FIELD_ID'],  # noqa: E501
    pole_number_global_field_id=yt_manager_config['YT_POLE_NUMBER_GLOBAL_FIELD_ID'],  # noqa: E501
    base_station_global_field_id=yt_manager_config['YT_BASE_STATION_GLOBAL_FIELD_ID'],  # noqa: E501
    email_datetime_global_field_id=yt_manager_config['YT_EMAIL_DATETIME_GLOBAL_FIELD_ID'],  # noqa: E501
    is_new_msg_global_field_id=yt_manager_config['YT_IS_NEW_MSG_GLOBAL_FIELD_ID'],  # noqa: E501
    sla_avr_deadline_global_field_id=yt_manager_config['YT_SLA_AVR_DEADLINE_GLOBAL_FIELD_ID'],  # noqa: E501
    is_sla_avr_expired_global_field_id=yt_manager_config['YT_IS_SLA_AVR_EXPIRED_GLOBAL_FIELD_ID'],  # noqa: E501
    sla_rvr_deadline_global_field_id=yt_manager_config['YT_SLA_RVR_DEADLINE_GLOBAL_FIELD_ID'],  # noqa: E501
    is_sla_rvr_expired_global_field_id=yt_manager_config['YT_IS_SLA_RVR_EXPIRED_GLOBAL_FIELD_ID'],  # noqa: E501
    avr_start_date_global_field_id=yt_manager_config['YT_AVR_START_DATE_FIELD_ID'],  # noqa: E501
    avr_end_date_global_field_id=yt_manager_config['YT_AVR_END_DATE_FIELD_ID'],  # noqa: E501
    rvr_start_date_global_field_id=yt_manager_config['YT_RVR_START_DATE_FIELD_ID'],  # noqa: E501
    rvr_end_date_global_field_id=yt_manager_config['YT_RVR_END_DATE_FIELD_ID'],  # noqa: E501
    dgu_start_date_global_field_id=yt_manager_config['YT_DGU_START_DATE_FIELD_ID'],  # noqa: E501
    dgu_end_date_global_field_id=yt_manager_config['YT_DGU_END_DATE_FIELD_ID'],  # noqa: E501
    operator_name_global_field_name=yt_manager_config['YT_OPERATOR_NAME_GLOBAL_FIELD_NAME'],  # noqa: E501
    avr_name_global_field_id=yt_manager_config['YT_AVR_NAME_GLOBAL_FIELD_ID'],  # noqa: E501
    monitoring_global_field_id=yt_manager_config['YT_MONITORING_GLOBAL_FIELD_ID'],  # noqa: E501
    type_of_incident_local_field_id=yt_manager_config['YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID'],  # noqa: E501
    subtype_of_incident_local_field_id=yt_manager_config['YT_SUBTYPE_OF_INCIDENT_LOCAL_FIELD_ID'],  # noqa: E501
    category_local_field_id=yt_manager_config['YT_CATEGORY_LOCAL_FIELD_ID'],  # noqa: E501
    on_generation_status_key=yt_manager_config['YT_ON_GENERATION_STATUS_KEY'],
    notify_op_issue_in_work_status_key=yt_manager_config['YT_NOTIFY_OPERATOR_ISSUE_IN_WORK_STATUS_KEY'],  # noqa: E501
    notified_op_issue_in_work_status_key=yt_manager_config['YT_NOTIFIED_OPERATOR_ISSUE_IN_WORK_STATUS_KEY'],  # noqa: E501
    notify_op_issue_closed_status_key=yt_manager_config['YT_NOTIFY_OPERATOR_ISSUE_CLOSED_STATUS_KEY'],  # noqa: E501
    notified_op_issue_closed_status_key=yt_manager_config['YT_NOTIFIED_OPERATOR_ISSUE_CLOSED_STATUS_KEY'],  # noqa: E501
    notify_contractor_in_work_status_key=yt_manager_config['YT_NOTIFY_CONTRACTOR_IN_WORK_STATUS_KEY'],  # noqa: E501
    notified_contractor_in_work_status_key=yt_manager_config['YT_NOTIFIED_CONTRACTOR_IN_WORK_STATUS_KEY'],  # noqa: E501
)
