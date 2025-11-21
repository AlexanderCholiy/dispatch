import os
from http import HTTPStatus
from typing import Optional

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest, HttpResponse, Http404, FileResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls.exceptions import Resolver404

from .constants import INLINE_EXTS, DJANGO_LOG_ROTATING_FILE
from users.views import role_required
from .loggers import LoggerFactory


django_logger = LoggerFactory(__name__, DJANGO_LOG_ROTATING_FILE).get_logger()


def bad_request(
    request: HttpRequest, exception: Optional[Exception] = None
) -> HttpResponse:
    return render(request, 'core/400.html', status=HTTPStatus.BAD_REQUEST)


def page_not_found(
    request: HttpRequest, exception: Resolver404 = None
) -> HttpResponse:
    current_site = get_current_site(request)
    path = f'{current_site}{request.path}'
    return render(
        request, 'core/404.html', {'path': path}, status=HTTPStatus.NOT_FOUND)


def permission_denied(
    request: HttpRequest, exception: Optional[Exception] = None
) -> HttpResponse:
    return render(request, 'core/403.html', status=HTTPStatus.FORBIDDEN)


def csrf_failure(request: HttpRequest, reason: str = '') -> HttpResponse:
    return render(
        request,
        'core/403csrf.html',
        {'reason': reason},
        status=HTTPStatus.FORBIDDEN
    )


def server_error(request: HttpRequest) -> HttpResponse:
    return render(
        request, 'core/500.html', status=HTTPStatus.INTERNAL_SERVER_ERROR
    )


def too_many_requests(
    request: HttpRequest, exception: Optional[Exception] = None
) -> HttpResponse:
    return render(
        request, 'core/429.html', status=HTTPStatus.TOO_MANY_REQUESTS
    )


@login_required
@role_required()
def protected_media(request: HttpRequest, file_path: str):
    """Отдача защищённых файлов через X-Accel-Redirect."""
    django_logger.info(f'[1] Запрос защищённого файла: {file_path}')

    if file_path.startswith('public/'):
        django_logger.warning('[2] Файл публичный — выбрасываем 404')
        raise Http404('Файл публичный, используйте прямую ссылку')

    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    django_logger.info(f'[2] Полный путь к файлу: {full_path}')

    if not os.path.exists(full_path):
        django_logger.error(
            f'[3] Файл {full_path} не найден — выбрасываем 404'
        )
        raise Http404('Файл не найден')

    ext = os.path.splitext(file_path)[1].lower()

    is_inline = ext in INLINE_EXTS
    filename = os.path.basename(file_path)

    # В разработке отдаем файл напрямую через Django:
    if settings.DEBUG:
        django_logger.info('[3] DEBUG=True — отдаём через FileResponse')
        return FileResponse(
            open(full_path, 'rb'),
            as_attachment=not is_inline,
            filename=filename
        )

    # В продакшене отдаём файл через Nginx:
    response = HttpResponse()
    redirect_url = f'/media/{file_path}'
    response['X-Accel-Redirect'] = redirect_url
    django_logger.info(
        f'[3] DEBUG=False — отдаём через X-Accel-Redirect: {redirect_url}'
    )

    if is_inline:
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

    response['Content-Type'] = ''
    django_logger.info(f'[4] Ответ возвращён: {response}')

    return response
