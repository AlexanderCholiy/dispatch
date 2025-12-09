import os
from http import HTTPStatus
from typing import Optional
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls.exceptions import Resolver404

from users.views import role_required

from .constants import INLINE_EXTS
from .loggers import django_logger


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
    """Отдача защищённых файлов через X-Accel-Redirect для продакшена."""
    normalized_path = os.path.normpath(file_path)

    if normalized_path.startswith('public/'):
        raise Http404('Файл публичный, используйте прямую ссылку')

    full_path = os.path.join(settings.MEDIA_ROOT, normalized_path)

    if not full_path.startswith(os.path.abspath(settings.MEDIA_ROOT)):
        django_logger.warning(
            f'Попытка доступа за пределы MEDIA_ROOT: {full_path}'
        )
        raise Http404('Файл не найден')

    if not os.path.exists(full_path):
        django_logger.warning(f'Файл {full_path} не найден')
        raise Http404('Файл не найден')

    ext = os.path.splitext(normalized_path)[1].lower()
    is_inline = ext in INLINE_EXTS
    filename = os.path.basename(normalized_path)

    # В разработке отдаем файл напрямую через Django:
    if settings.DEBUG:
        return FileResponse(
            open(full_path, 'rb'),
            as_attachment=not is_inline,
            filename=filename
        )

    # Кодируем каждый сегмент пути для URL
    safe_path = '/'.join(quote(part) for part in normalized_path.split('/'))
    redirect_url = f'/media/{safe_path}'

    # В продакшене отдаём файл через Nginx:
    response = HttpResponse()
    response['X-Accel-Redirect'] = redirect_url

    # Кодируем имя файла для Content-Disposition
    filename_ascii = filename.encode('ascii', 'ignore').decode() or 'file'
    filename_rfc5987 = quote(filename)

    disposition_type = 'inline' if is_inline else 'attachment'
    disposition = (
        f'{disposition_type}; '
        f'filename="{filename_ascii}"; '
        f'filename*=UTF-8\'\'{filename_rfc5987}'
    )

    response['Content-Disposition'] = disposition
    response['Content-Type'] = ''

    return response
