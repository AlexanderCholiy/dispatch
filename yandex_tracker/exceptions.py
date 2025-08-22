from requests.exceptions import RequestException


class YandexTrackerCriticalErr(RequestException):
    def __init__(self, status_code: int | str, message: str = ''):
        self.status_code = status_code
        self.message = message or 'ошибка при обращении к API Yandex Tracker.'
        super().__init__(f'Ошибка {status_code}: {self.message}')


class YandexTrackerWarningErr(YandexTrackerCriticalErr):
    pass
