from requests.exceptions import RequestException


class YandexTrackerAuthErr(RequestException):
    def __init__(self, status_code: int | str, message: str = ''):
        self.status_code = status_code
        self.message = message or 'ошибка при аунтификации API Yandex Tracker.'
        super().__init__(f'Ошибка {status_code}: {self.message}')
