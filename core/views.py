from http import HTTPStatus
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote

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


def send_x_accel_file(file_path: Path | str) -> HttpResponse:
    file_path = Path(unquote(str(file_path)))
    media_root = Path(settings.MEDIA_ROOT).resolve()

    if file_path.is_absolute():
        full_path = file_path.resolve()
        try:
            normalized_path = full_path.relative_to(media_root).as_posix()
        except ValueError:
            django_logger.warning(
                'Попытка доступа к абсолютному пути вне MEDIA_ROOT: '
                f'{full_path}'
            )
            raise Http404('Некорректный путь к файлу')
    else:
        normalized_path = file_path.as_posix().lstrip('/')
        full_path = (media_root / normalized_path).resolve()

    try:
        full_path.relative_to(media_root)
    except ValueError:
        django_logger.warning(f'Попытка обхода путей: {file_path}')
        raise Http404('Некорректный путь к файлу')

    if not full_path.exists():
        django_logger.warning(f'Файл не найден: {file_path}')
        raise Http404('Файл не найден')

    filename = full_path.name
    is_inline = full_path.suffix.lower() in INLINE_EXTS

    if settings.DEBUG:
        return FileResponse(open(full_path, 'rb'), as_attachment=not is_inline)

    safe_path = '/'.join(quote(part) for part in normalized_path.split('/'))
    redirect_url = f"{settings.MEDIA_URL}{safe_path}"

    response = HttpResponse()
    response['X-Accel-Redirect'] = redirect_url

    filename_ascii = filename.encode('ascii', 'ignore').decode() or 'file'
    filename_rfc5987 = quote(filename)

    disposition = (
        f'{"inline" if is_inline else "attachment"}; '
        f'filename="{filename_ascii}"; '
        f"filename*=UTF-8''{filename_rfc5987}"
    )

    response['Content-Disposition'] = disposition
    response['Content-Type'] = ''

    return response


@login_required
@role_required()
def protected_media(request: HttpRequest, file_path: Path | str):
    return send_x_accel_file(file_path)
