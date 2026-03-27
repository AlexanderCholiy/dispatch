import os
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit
from stream_zip import ZIP_32, ZIP_64, stream_zip

from core.constants import DATETIME_LOCAL_FORMAT, ZIP64_THRESHOLD
from core.services.get_max_today_datetime import get_max_today_datetime
from core.validators import get_aware_datetime
from users.utils import role_required

from .constants import (
    EMAILS_PER_PAGE,
    MAX_EMAILS_INFO_CACHE_SEC,
    PAGE_SIZE_EMAILS_CHOICES,
)
from .models import (
    EmailAttachment,
    EmailFolder,
    EmailInTextAttachment,
    EmailMessage,
)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def emails_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()

    folder_name = (
        request.GET.get('folder', '').strip()
        or request.COOKIES.get('folder', '').strip()
    )

    email_from = (
        request.GET.get('email_from', '').strip()
        or request.COOKIES.get('email_from', '').strip()
    )

    date_from = (
        request.GET.get('email_date_from', '').strip()
        or request.COOKIES.get('email_date_from', '').strip()
        or None
    )
    date_from = get_aware_datetime(date_from)

    date_to = (
        request.GET.get('email_date_to', '').strip()
        or request.COOKIES.get('email_date_to', '').strip()
        or None
    )
    date_to = get_aware_datetime(date_to)

    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    per_page = int(
        request.GET.get('per_page')
        or request.COOKIES.get('per_page_emails')
        or EMAILS_PER_PAGE
    )

    sort = (
        request.GET.get('sort_emails')
        or request.COOKIES.get('sort_emails')
        or 'desc'
    )

    if per_page not in PAGE_SIZE_EMAILS_CHOICES:
        params = request.GET.copy()
        params['per_page'] = EMAILS_PER_PAGE
        return redirect(f"{request.path}?{params.urlencode()}")

    base_qs = (
        EmailMessage.objects
        .exclude(email_incident__isnull=True)
    )

    if query:
        filters = (
            Q(email_incident__code=query)
            | Q(email_subject__icontains=query)
        )
        if query.isdigit():
            filters |= Q(pk=int(query))

        base_qs = base_qs.filter(filters).distinct()

    if folder_name:
        base_qs = base_qs.filter(folder__name=folder_name)

    if email_from:
        base_qs = base_qs.filter(email_from=email_from)

    if date_from:
        base_qs = base_qs.filter(email_date__gte=date_from)

    if date_to:
        base_qs = base_qs.filter(email_date__lte=date_to)

    if sort == 'asc':
        base_qs = base_qs.order_by('email_date', 'is_first_email', 'id')
    else:
        base_qs = base_qs.order_by('-email_date', 'is_first_email', 'id')

    paginator = Paginator(base_qs.values_list('id', flat=True), per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_ids = list(page_obj.object_list)

    emails_qs = EmailMessage.objects.filter(id__in=page_ids).select_related(
        'email_incident',
        'folder',
        'email_mime',
    ).prefetch_related(
        Prefetch(
            'email_attachments', to_attr='prefetched_attachments'
        ),
        Prefetch(
            'email_intext_attachments', to_attr='prefetched_intext_attachments'
        ),
        Prefetch(
            'email_msg_to', to_attr='prefetched_to'
        ),
        Prefetch(
            'email_msg_cc', to_attr='prefetched_cc'
        ),
    )
    id_index = {id_: i for i, id_ in enumerate(page_ids)}
    emails = sorted(emails_qs, key=lambda n: id_index[n.id])

    folders = cache.get_or_set(
        'email_filter_folders',
        lambda: list(
            EmailFolder.objects.values_list('name', flat=True)
            .distinct()
            .order_by('name')
        ),
        MAX_EMAILS_INFO_CACHE_SEC,
    )

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    context = {
        'page_obj': page_obj,
        'emails': emails,
        'search_query': query,
        'page_url_base': page_url_base,
        'folders': folders,
        'selected': {
            'folder': folder_name,
            'email_from': email_from,
            'date_from': (
                date_from.strftime(DATETIME_LOCAL_FORMAT) if date_from else ''
            ),
            'date_to': (
                date_to.strftime(DATETIME_LOCAL_FORMAT) if date_to else ''
            ),
            'per_page': per_page,
            'sort': sort,
        },
        'page_size_choices': PAGE_SIZE_EMAILS_CHOICES,
        'max_datetime': get_max_today_datetime(),
    }

    return render(request, 'emails/emais_list.html', context)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def download_email_attachments(
    request: HttpRequest, email_id: int
) -> StreamingHttpResponse:
    """
    Генерирует и отдает ZIP-архив со всеми вложениями инцидента на лету.
    Не сохраняет архив на диск.
    """
    try:
        email_msg = EmailMessage.objects.prefetch_related(
            'email_attachments',
            'email_intext_attachments',
        ).get(id=email_id)
    except EmailMessage.DoesNotExist:
        raise Http404('Email не найден')

    files_data = []
    total_uncompressed_size = 0

    all_attachments: list[EmailAttachment | EmailInTextAttachment] = (
        list(email_msg.email_attachments.all())
        + list(email_msg.email_intext_attachments.all())
    )

    for att in all_attachments:
        if not att.file_url:
            continue

        if not att.file_url.storage.exists(att.file_url.name):
            continue

        file_path = att.file_url.path
        zip_name = os.path.basename(att.file_url.name)

        stat = os.stat(file_path)
        file_size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime)

        total_uncompressed_size += file_size

        files_data.append({
            'path': file_path,
            'name': zip_name,
            'size': file_size,
            'mtime': mtime
        })

    if not files_data:
        raise Http404('Нет доступных вложений для скачивания')

    archive_format = (
        ZIP_64 if total_uncompressed_size > ZIP64_THRESHOLD else ZIP_32
    )

    def file_entries_generator():
        for f_info in files_data:
            yield (
                f_info['name'],
                f_info['mtime'],
                0o644,
                archive_format,
                open(f_info['path'], 'rb')
            )

    entries = file_entries_generator()

    archive_name = f'email_{email_id}_attachments.zip'

    response = StreamingHttpResponse(
        stream_zip(entries),
        content_type='application/x-zip-compressed'
    )

    response['Content-Disposition'] = f'attachment; filename="{archive_name}"'

    return response
