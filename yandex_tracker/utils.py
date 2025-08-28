import inspect
import os
import re
from datetime import datetime, timedelta
from http import HTTPMethod, HTTPStatus
from typing import Optional

import requests
from django.db import models
from django.utils import timezone

from core.constants import YANDEX_TRACKER_ROTATING_FILE
from core.loggers import LoggerFactory
from core.utils import Config
from core.wraps import safe_request
from emails.models import EmailMessage
from emails.utils import EmailManager
from incidents.models import Incident

from .constants import INCIDENTS_REGION_NOT_FOR_YT, MAX_ATTACHMENT_SIZE_IN_YT
from .exceptions import YandexTrackerAuthErr
from .validators import normalize_text_with_json

yt_manager_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger

yt_manager_config = {
    'YT_CLIENT_ID': os.getenv('YT_CLIENT_ID'),
    'YT_CLIENT_SECRET': os.getenv('YT_CLIENT_SECRET'),
    'YT_ACCESS_TOKEN': os.getenv('YT_ACCESS_TOKEN'),
    'YT_REFRESH_TOKEN': os.getenv('YT_REFRESH_TOKEN'),
    'YT_ORGANIZATION_ID': os.getenv('YT_ORGANIZATION_ID'),
    'YT_QUEUE': os.getenv('YT_QUEUE'),
    'YT_DATABASE_GLOBAL_FIELD_ID': os.getenv('YT_DATABASE_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_POLE_NUMBER_GLOBAL_FIELD_ID': os.getenv('YT_POLE_NUMBER_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_BASE_STATION_GLOBAL_FIELD_ID': os.getenv('YT_BASE_STATION_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_EMAIL_DATETIME_GLOBAL_FIELD_ID': os.getenv('YT_EMAIL_DATETIME_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_IS_NEW_MSG_GLOBAL_FIELD_ID': os.getenv('YT_IS_NEW_MSG_GLOBAL_FIELD_ID'),  # noqa: E501
    'YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID': os.getenv('YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID'),  # noqa: E501
}
Config.validate_env_variables(yt_manager_config)


class YandexTrackerManager:
    retries = 3
    timeout = 30

    current_user_url = 'https://api.tracker.yandex.net/v2/myself'
    token_url = 'https://oauth.yandex.ru/token'
    search_issues_url = (
        'https://api.tracker.yandex.net/v2/issues/_search?expand=transitions')
    all_users_url = 'https://api.tracker.yandex.net/v2/users'
    temporary_file_url = 'https://api.tracker.yandex.net/v2/attachments/'
    create_issue_url = 'https://api.tracker.yandex.net/v2/issues/'
    filter_issues_url = 'https://api.tracker.yandex.net/v2/issues/_search'
    statuses_url = 'https://api.tracker.yandex.net/v2/statuses'

    closed_status_types: set[str] = {'closed', 'done', 'resolved'}

    def __init__(
        self,
        cliend_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        organisation_id: str,
        queue: str,
        database_global_field_id: str,
        pole_number_global_field_id: str,
        base_station_global_field_id: str,
        email_datetime_global_field_id: str,
        is_new_msg_global_field_id: str,
        type_of_incident_local_field_id: str,
    ):
        self.client_id = cliend_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.queue = queue
        self.organisation_id = organisation_id

        self.database_global_field_id = database_global_field_id
        self.pole_number_global_field_id = pole_number_global_field_id
        self.base_station_global_field_id = base_station_global_field_id
        self.email_datetime_global_field_id = email_datetime_global_field_id
        self.is_new_msg_global_field_id = is_new_msg_global_field_id

        self.type_of_incident_local_field_id = type_of_incident_local_field_id

        self._current_user_uid: Optional[str] = None
        self.local_fields_url = (
            f'https://api.tracker.yandex.net/v3/queues/{queue}/localFields')

    def find_yt_number_in_text(self, text: str) -> list[str]:
        return re.findall(rf'{self.queue}-\d+', text)

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
        добавлены в YandexTracker, или письма для которых сформирован инцидент,
        определен шифр опоры из темы или тела письма и эти опоры НЕ находятся в
        указанном регионе INCIDENTS_REGION_NOT_FOR_YT.

        Исключаем инциденты без ответственного диспетчера и старше N дней
        назад, чтобы не добавлять неактуальные инциденты при смене основного
        фильтра.

        Args:
            days (days): Количество дней назад, для фильтрации инцидентов не
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
            email_incident__pole__isnull=False,
        ).exclude(
            email_incident__pole__region__in=INCIDENTS_REGION_NOT_FOR_YT
        )

        exclusion_date = timezone.now() - timedelta(days=days)

        emails = (
            emails_not_in_yt | emails_with_incidents_in_yt
        ).exclude(
            models.Q(email_incident__responsible_user__isnull=True)
            & models.Q(email_incident__incident_date__lt=exclusion_date)
        ).distinct().order_by(
            'email_incident_id', 'is_first_email', 'email_date', 'id'
        )
        return emails

    @safe_request(yt_manager_logger, retries=retries, timeout=timeout)
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
            yt_manager_logger.info('Токен устарел, обновляем.')
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
        return {
            user['login']: user['uid'] for user in self.users_info
            if not user['disableNotifications']
        }

    @property
    def users_info(self) -> list[dict]:
        """Список всех пользователей в Yandex Tracker."""
        return self._make_request(
            HTTPMethod.GET,
            self.all_users_url,
            sub_func_name=inspect.currentframe().f_code.co_name
        )

    @property
    def all_statuses(self) -> list[dict]:
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

    def delete_comment(self, issue_key: str, comment_id: int) -> dict:
        url = f'{self.create_issue_url}{issue_key}/comments/{comment_id}'
        return self._make_request(
            HTTPMethod.DELETE,
            url,
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
            size = os.path.getsize(filepath)
            if size > MAX_ATTACHMENT_SIZE_IN_YT:
                yt_manager_logger.warning(
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
                yt_manager_logger.error(
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
            email_datetime, datetime) else None

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
            self.is_new_msg_global_field_id: 'True',
        }

        add_payload = {
            'queue': self.queue,
            'type': issue_type,
            'author': author,
            'assignee': assignee,
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

    def select_issue_comments(self, issue_key: str) -> list[dict]:
        url = f'{self.create_issue_url}{issue_key}/comments'
        return self._make_request(
            HTTPMethod.GET,
            url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def _comment_like_email(self, email: EmailMessage) -> str:
        email_to = [
            eml.email_to for eml in email.email_msg_to.all()
        ]
        email_cc = [
            eml.email_to for eml in email.email_msg_cc.all()
        ]
        comment_like_email = (
            f'**From:** {email.email_from}\n'
            f'**To:** {', '.join(email_to)}\n'
        )
        if email_cc:
            comment_like_email += f'**Cc:** {', '.join(email_cc)}\n'

        # Будем использовать временную зону указанную в настройках Django:
        email_date_moscow = email.email_date.astimezone(
            timezone.get_current_timezone())
        comment_like_email += f'**Date:** {email_date_moscow}\n'

        if email.email_subject:
            subject = normalize_text_with_json(email.email_subject)
            comment_like_email += f'**Subject:** {subject}\n\n'
        if email.email_body:
            comment_like_email += normalize_text_with_json(email.email_body)

        return comment_like_email

    def add_issue_email_comment(self, email: EmailMessage, issue_key: str):
        """Создаёт комментарий по email, которого ещё нет в YandexTracker."""
        email_is_not_exist = True

        for comment in self.select_issue_comments(issue_key):
            comment_usr_uid = str(comment['createdBy']['id'])
            comment_text = comment.get('text', '').strip()
            if comment_usr_uid == self.current_user_uid:
                if comment_text == self._comment_like_email(email):
                    email_is_not_exist = False
                    break

        if email_is_not_exist:
            temp_files = self.download_email_temp_files(email)
            comment = self._comment_like_email(email)
            self.create_comment(issue_key, comment, temp_files)

    def _prepare_data_from_email(self, email_incident: EmailMessage) -> dict:
        """Подготовка данных для отправки в YandexTracker."""
        incident: Incident = email_incident.email_incident
        database_id: int = incident.pk

        summary = normalize_text_with_json(
            email_incident.email_subject
        ) if email_incident.email_subject else f'Инцидент №{database_id}'

        description = normalize_text_with_json(
            email_incident.email_body
        ) if email_incident.email_body else None

        pole_number = incident.pole.pole if incident.pole else None
        base_station_number = (
            incident.base_station.bs_name) if incident.base_station else None

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

    def add_incident_to_yandex_tracker(
        self, email_incident: EmailMessage, is_first_email: bool
    ):
        """Создание инцидента в YandexTracker."""
        data_for_yt = self._prepare_data_from_email(email_incident)
        issues: list[dict] = data_for_yt['issues']
        key = issues[0]['key'] if issues else None

        # Инцидент только пришел и ещё отсутствует в YandexTracker:
        if not issues and is_first_email:
            temp_files = self.download_email_temp_files(email_incident)
            self.create_or_update_issue(
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
        # Инцидент отсутствует в YandexTracker, но по нему пришло уточнение,
        # поэтому надо восстановить полностью цепочку писем для инцидента:
        elif not issues and not is_first_email:
            all_email_incident = EmailMessage.objects.filter(
                email_incident=email_incident.email_incident
            ).order_by('is_first_email', 'email_date', 'id')

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
            key: str = issue['key']
            for email in all_email_incident[1:]:
                self.add_issue_email_comment(email, key)
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
                if is_first_email:
                    temp_files = self.download_email_temp_files(email_incident)
                    self.create_or_update_issue(
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
                    self.add_issue_email_comment(email_incident, key)

    def filter_issues(self, yt_filter: dict, days_ago: int = 7) -> list[dict]:
        page = 1
        per_page = 100
        all_issues = []
        now: datetime = timezone.now()
        days_ago: datetime = now - timedelta(days=days_ago)
        yt_filter['queue'] = self.queue
        yt_filter['createdAt'] = {
            'from': days_ago.isoformat(),
            'to': now.isoformat()
        }
        payload = {'filter': yt_filter}

        while True:
            params = {
                'page': page,
                'perPage': per_page
            }
            batch = self._make_request(
                HTTPMethod.POST,
                self.filter_issues_url,
                json=payload,
                params=params,
                sub_func_name=inspect.currentframe().f_code.co_name,
            )
            if not batch:
                break

            all_issues.extend(batch)
            page += 1

        return all_issues

    def closed_issues(self, days_ago: int = 7) -> list[dict]:
        closed_statuses: list[str] = [
            status['key']
            for status in self.all_statuses
            if status['type'] in self.closed_status_types
        ]
        return self.filter_issues({'status': closed_statuses}, days_ago)

    def unclosed_issues(self, days_ago: int = 7) -> list[dict]:
        unclosed_statuses: list[str] = [
            status['key']
            for status in self.all_statuses
            if status['type'] not in self.closed_status_types
        ]
        return self.filter_issues({'status': unclosed_statuses}, days_ago)

    @property
    def all_local_fields(self) -> list[dict]:
        return self._make_request(
            HTTPMethod.GET,
            self.local_fields_url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def select_local_field(
        self, local_field_id: str
    ) -> Optional[dict]:
        return next((
            field for field in self.all_local_fields
            if field['id'].endswith(local_field_id)
        ), None)


yt_manager = YandexTrackerManager(
    cliend_id=yt_manager_config['YT_CLIENT_ID'],
    client_secret=yt_manager_config['YT_CLIENT_SECRET'],
    access_token=yt_manager_config['YT_ACCESS_TOKEN'],
    refresh_token=yt_manager_config['YT_REFRESH_TOKEN'],
    organisation_id=yt_manager_config['YT_ORGANIZATION_ID'],
    queue=yt_manager_config['YT_QUEUE'],
    database_global_field_id=yt_manager_config['YT_DATABASE_GLOBAL_FIELD_ID'],
    pole_number_global_field_id=yt_manager_config['YT_POLE_NUMBER_GLOBAL_FIELD_ID'],  # noqa: E501
    base_station_global_field_id=yt_manager_config['YT_BASE_STATION_GLOBAL_FIELD_ID'],  # noqa: E501
    email_datetime_global_field_id=yt_manager_config['YT_EMAIL_DATETIME_GLOBAL_FIELD_ID'],  # noqa: E501
    is_new_msg_global_field_id=yt_manager_config['YT_IS_NEW_MSG_GLOBAL_FIELD_ID'],  # noqa: E501
    type_of_incident_local_field_id=yt_manager_config['YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID'],  # noqa: E501
)
