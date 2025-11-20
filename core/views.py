import os
from http import HTTPStatus
from typing import Optional

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest, HttpResponse, Http404, FileResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls.exceptions import Resolver404

from .constants import INLINE_EXTS
from users.views import role_required


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
    if file_path.startswith('public/'):
        raise Http404('Файл публичный, используйте прямую ссылку')

    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    if not os.path.exists(full_path):
        raise Http404('Файл не найден')

    ext = os.path.splitext(file_path)[1].lower()

    is_inline = ext in INLINE_EXTS
    filename = os.path.basename(file_path)

    # В разработке отдаем файл напрямую через Django:
    if settings.DEBUG:
        return FileResponse(
            open(full_path, 'rb'),
            as_attachment=not is_inline,
            filename=filename
        )

    # В продакшене отдаём файл через Nginx:
    response = HttpResponse()
    response['X-Accel-Redirect'] = f'/media/{file_path}'
    response['Content-Type'] = ''

    if is_inline:
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response
