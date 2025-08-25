
import re
import inspect
import requests
from typing import Optional
from http import HTTPStatus, HTTPMethod

from emails.models import EmailMessage
from core.constants import YANDEX_TRACKER_ROTATING_FILE
from core.loggers import LoggerFactory
from .exceptions import YandexTrackerAuthErr
from core.wraps import safe_request


yt_manager_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class YandexTrackerManager:
    retries = 3
    timeout = 30

    current_user_url = 'https://api.tracker.yandex.net/v2/myself'
    token_url = 'https://oauth.yandex.ru/token'
    search_issues_url = (
        'https://api.tracker.yandex.net/v2/issues/_search?expand=transitions')

    def __init__(
        self,
        cliend_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        organisation_id: str,
        queue: str,
        database_global_field_id: str,
    ):
        self.client_id = cliend_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.queue = queue
        self.organisation_id = organisation_id
        self.database_global_field_id = database_global_field_id

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
    def current_user_info(self) -> dict:
        """Возвращает информацию о текущем пользователе в Яндекс.Трекере."""
        return self._make_request(
            HTTPMethod.GET,
            self.current_user_url,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )

    def select_issue(
        self, database_id: Optional[int] = None, key: Optional[str] = None
    ) -> list[dict]:
        """Поиск задачи по глобальному полю database_id или по её ключу key."""

        if database_id is None and key is None:
            raise ValueError(
                'Необходимо указать или database_id или ключ задачи.'
            )
        filter = {'queue': self.queue}

        if database_id is not None:
            filter[YT_DATABASE_ID_GLOBAL_FIELD_NAME] = database_id

        if key is not None:
            filter['key'] = key

        payload = {'filter': filter}

        return self._make_request(
            HTTPMethod.POST,
            self.search_issues_url,
            json=payload,
            sub_func_name=inspect.currentframe().f_code.co_name,
        )
