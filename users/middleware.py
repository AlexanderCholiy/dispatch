from http import HTTPStatus

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.shortcuts import redirect


class SafeSessionMiddleware(SessionMiddleware):
    """
    SafeSessionMiddleware — расширение стандартного Django SessionMiddleware,
    предназначенное для безопасной обработки исключения SessionInterrupted.

    В Django SessionInterrupted выбрасывается в момент сохранения сессии
    (SessionMiddleware.process_response), если сессия была удалена или
    изменена в параллельном запросе. Типичный сценарий:
        - пользователь разлогинился в другой вкладке
        - истекла сессия
        - несколько gunicorn/uwsgi воркеров используют Redis/DB sessions
        - race condition при одновременных запросах

    По умолчанию Django считает это критической ошибкой и возвращает 500,
    что плохо влияет на UX и может ломать SPA/API клиентов.

    Этот middleware:
        - перехватывает SessionInterrupted
        - для API-запросов возвращает HTTP 401 (чтобы фронт корректно
        обработал logout)
        - для web-интерфейса выполняет logout и редиректит на LOGIN_URL
        - предотвращает появление 500 ошибок из-за race conditions сессий

    Используется вместо стандартного
    django.contrib.sessions.middleware.SessionMiddleware.
    """

    def process_response(self, request, response):
        try:
            return super().process_response(request, response)
        except SessionInterrupted:
            if request.path.startswith('/api/'):
                return HttpResponse(status=HTTPStatus.UNAUTHORIZED)
            logout(request)
            return redirect(settings.LOGIN_URL)
