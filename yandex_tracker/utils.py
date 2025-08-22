
import os
import re
import time
import requests
from typing import Optional
from http import HTTPStatus

from emails.models import EmailMessage
from .constants import (
    YT_QUEUE, YT_ACCESS_TOKEN, YT_REFRESH_TOKEN, YT_ORGANIZATION_ID
)
from core.constants import YANDEX_TRACKER_ROTATING_FILE
from core.loggers import LoggerFactory
from .exceptions import YandexTrackerCriticalErr, YandexTrackerWarningErr


yt_manager_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class YandexTrackerManager:
    CURRENT_USER_URL = 'https://api.tracker.yandex.net/v2/myself'

    def __init__(
        self,
        access_token: str = YT_ACCESS_TOKEN,
        refresh_token: str = YT_REFRESH_TOKEN,
        organisation_id: str = YT_ORGANIZATION_ID,
        incident_queue: str = YT_QUEUE,
        timeout: int = 30,
        retries: int = 2
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.incident_queue = incident_queue
        self.organisation_id = organisation_id
        self.timeout = timeout
        self.retries = retries

    @staticmethod
    def find_yt_number_in_text(text: str) -> list[str]:
        return re.findall(rf'{YT_QUEUE}-\d+', text)

    @property
    def headers(self):
        return {
            'Authorization': f'OAuth {self.access_token}',
            'X-Org-Id': self.organisation_id,
        }

    @property
    def check_token(self) -> bool:
        response = requests.get(
            self.CURRENT_USER_URL, headers=self.headers, timeout=self.timeout
        )
        return response.status_code == HTTPStatus.OK

    @property
    def current_user_info(self) -> dict:
        retry_count = 0
        while retry_count <= self.retries:
            retry_count += 1
            try:
                with requests.get(
                    self.CURRENT_USER_URL,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                        retry_after = int(
                            response.headers.get('Retry-After', 10)
                        )
                        time.sleep(retry_after)
                    elif response.status_code == HTTPStatus.OK:
                        if response.status_code == HTTPStatus.NO_CONTENT:
                            return {}
                        return response.json()
                    else:
                        yt_manager_logger.critical(
                            f'Ошибка {response.status_code}: {response.text}'
                        )
                        raise YandexTrackerCriticalErr(
                            response.status_code, response.text
                        )

            except requests.exceptions.Timeout:
                yt_manager_logger.warning(
                    f'Таймаут при запросе к {self.CURRENT_USER_URL}')
                raise YandexTrackerWarningErr(
                    HTTPStatus.REQUEST_TIMEOUT,
                    'Истекло время ожидания ответа от сервера.'
                )

            except requests.exceptions.RequestException as e:
                yt_manager_logger.exception('Ошибка запроса')
                raise YandexTrackerCriticalErr(
                    HTTPStatus.INTERNAL_SERVER_ERROR, str(e)
                )

            raise YandexTrackerCriticalErr(
                HTTPStatus.TOO_MANY_REQUESTS,
                'Максимальное количество попыток исчерпано.'
            )
