import requests
from requests.exceptions import RequestException
from http import HTTPStatus

from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


from core.loggers import max_api_logger
from max.constants import MAX_TOKEN, MAX_CERT_DIR


class MaxApi:

    BASE_URL = 'https://platform-api2.max.ru'
    UPDATES_URL = f"{BASE_URL}/updates"
    ENDPOINT_MESSAGES = f"{BASE_URL}/messages"

    # Ссылки на актуальные сертификаты Минцифры:
    CERT_URLS = [
        'https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt',
        'https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt'
    ]

    def __init__(
        self,
        token: str,
        cert_filename: str = 'russian_trusted_root_ca.pem',
    ):
        self.headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
        }

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
            response = self.session.get(url, verify=False, timeout=10)
            if response.status_code == HTTPStatus.OK:
                bundle_content += response.content + b'\n'
            else:
                raise RequestException(
                    f'Сервер Госуслуг вернул статус {response.status_code}'
                )

        self.cert_path.write_bytes(bundle_content)

    def check_updates(self):
        """Запрашиваем список последних событий бота"""
        response = self.session.get(
            self.UPDATES_URL,
            verify=self.cert_path,
            timeout=15
        )

        if response.status_code == HTTPStatus.OK:
            updates: list[dict] = response.json()

            print(updates)

            if not updates:
                max_api_logger.warning(
                    'Событий нет. '
                    'Зайдите в MAX и напишите что-нибудь боту / запустите его.'
                )
                return

            for update in updates:
                chat_id = update.get('chat_id')
                update_type = update.get('update_type')
                max_api_logger.info(
                    f'Найдено событие "{update_type}" для chat_id: {chat_id}'
                )
        else:
            raise RequestException(
                f'Ошибка отправки ({response.status_code})\n{response.text}'
            )

    def send_message(self, chat_id: int, text: str):
        """Функция для отправки сообщения пользователю."""
        url = f'{self.BASE_URL}/messages'

        payload = {
            'chat_id': chat_id,
            'text': text,
            'format': 'markdown'
        }

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code == HTTPStatus.OK:
            max_api_logger.debug('Сообщение успешно отправлено.')
        else:
            raise RequestException(
                f'Ошибка отправки ({response.status_code})\n{response.text}'
            )


max_api = MaxApi(token=MAX_TOKEN)
