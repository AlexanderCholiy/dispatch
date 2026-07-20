from datetime import datetime, timezone
from http import HTTPStatus
from typing import TypedDict

import requests
from django.utils import timezone as django_timezone
from requests import Response
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util import Retry

from core.loggers import max_api_logger
from max.constants import MAX_CERT_DIR, MAX_TOKEN


class BotInfo(TypedDict):
    user_id: int
    username: str
    last_activity_time: datetime
    name: str | None
    description: str | None


class LastUpdate(TypedDict):
    chat_id: int
    text: str
    sender_name: str
    timestamp: datetime


class MessageInfo(TypedDict):
    mid: str  # Уникальный ID сообщения
    chat_id: int
    text: str
    timestamp: datetime


class MaxApi:

    BASE_URL = 'https://platform-api2.max.ru'
    UPDATES_URL = f'{BASE_URL}/updates'
    CHATS_URL = f'{BASE_URL}/chats'
    MESSAGES_URL = f'{BASE_URL}/messages'
    BOT_INFO_URL = f'{BASE_URL}/me'

    # Ссылки на актуальные сертификаты Минцифры:
    CERT_URLS = [
        'https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt',
        'https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt'
    ]

    def __init__(
        self,
        token: str,
        cert_filename: str = 'russian_trusted_root_ca.pem',
        request_timeout: int = 15,
    ):
        self.headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
        }

        self.request_timeout = request_timeout

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            ],
            raise_on_status=False,
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

        self.cert_path = MAX_CERT_DIR / cert_filename
        self._ensure_certificate()

        self._bot_info = None

    @staticmethod
    def timestamp_to_datetime(timestamp: int) -> datetime:
        timestamp_utc = datetime.fromtimestamp(
            timestamp / 1000, tz=timezone.utc
        )
        return django_timezone.localtime(timestamp_utc)

    def _prepare_response(self, response: Response):
        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            raise RequestException(
                f'Ошибка отправки ({response.status_code})\n{response.text}'
            )

    def _ensure_certificate(self):
        """
        Проверяет наличие файла сертификата.
        Если его нет, скачивает и собирает бандл.
        """
        if self.cert_path.exists():
            return

        max_api_logger.debug(f'Файл сертификата {self.cert_path} не найден.')
        self.cert_path.parent.mkdir(parents=True, exist_ok=True)

        bundle_content = b''
        for url in self.CERT_URLS:
            response = self.session.get(
                url, verify=False, timeout=self.request_timeout
            )
            if response.status_code == HTTPStatus.OK:
                bundle_content += response.content + b'\n'
            else:
                raise RequestException(
                    f'Сервер Госуслуг вернул статус {response.status_code}'
                )

        self.cert_path.write_bytes(bundle_content)

    def get_bot_info(self) -> BotInfo:
        response = self.session.get(
            self.BOT_INFO_URL,
            verify=self.cert_path,
            timeout=self.request_timeout,
        )

        result: dict = self._prepare_response(response)
        dt_local = self.timestamp_to_datetime(result['last_activity_time'])

        return {
            'user_id': int(result['user_id']),
            'username': str(result['username']),
            'last_activity_time': dt_local,
            'name': result.get('name'),
            'description': result.get('description'),

        }

    @property
    def bot_info(self) -> BotInfo:
        if not self._bot_info:
            self._bot_info = self.get_bot_info()

        return self._bot_info

    def get_last_update(self) -> LastUpdate:
        """Запрашиваем список последних событий бота"""
        print(
            'Зайдите в MAX и напишите что-нибудь боту '
            f'{self.bot_info["name"]} ({self.bot_info["username"]}).'
        )

        response = self.session.get(
            self.UPDATES_URL,
            verify=self.cert_path,
            timeout=self.request_timeout,
        )

        result = self._prepare_response(response)

        if not result:
            max_api_logger.warning(
                'Событий нет. '
                'Зайдите в MAX и напишите что-нибудь боту '
                f'{self.bot_info["name"]} ({self.bot_info["username"]}).'
            )

        updates = result['updates']
        sorted_updates = sorted(
            updates, key=lambda x: x['timestamp'], reverse=True
        )
        last_update: dict = sorted_updates[0]

        chat_id = (
            last_update['message']['recipient']['chat_id']
        )
        text = last_update.get('message', {}).get('body', {}).get('text')
        sender_name = (
            last_update.get('message', {}).get('sender', {}).get('name')
        )
        timestamp = self.timestamp_to_datetime(last_update['timestamp'])

        return {
            'chat_id': chat_id,
            'text': text,
            'sender_name': sender_name,
            'timestamp': timestamp,
        }

    def get_chats_info(self) -> dict:
        response = self.session.get(
            self.CHATS_URL,
            verify=self.cert_path,
            timeout=self.request_timeout,
        )
        return self._prepare_response(response)

    def send_message(
        self,
        text: str,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> MessageInfo:
        """Функция для отправки сообщения пользователю или чату."""
        payload = {
            'text': text,
            'format': 'markdown'
        }

        params = {}
        if chat_id:
            params['chat_id'] = chat_id
        elif user_id:
            params['user_id'] = user_id
        else:
            raise ValueError('Нужно указать chat_id или user_id')

        response = self.session.post(
            self.MESSAGES_URL,
            json=payload,
            params=params,
            headers=self.headers,
            verify=self.cert_path,
            timeout=self.request_timeout,
        )

        result: dict = self._prepare_response(response)

        mid = result['message']['body']['mid']
        chat_id = result['message']['recipient']['chat_id']
        text = result['message']['body']['text']
        timestamp = self.timestamp_to_datetime(result['message']['timestamp'])

        return {
            'mid': mid,
            'chat_id': chat_id,
            'text': text,
            'timestamp': timestamp,
        }


max_api = MaxApi(token=MAX_TOKEN)
