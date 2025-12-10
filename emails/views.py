from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit

from users.utils import role_required

from .constants import (
    EMAILS_PER_PAGE,
    MAX_EMAILS_INFO_CACHE_SEC,
    PAGE_SIZE_EMAILS_CHOICES,
)
from .models import EmailFolder, EmailMessage


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

    if sort == 'asc':
        base_qs = base_qs.order_by('email_date', 'is_first_email', 'id')
    else:
        base_qs = base_qs.order_by('-email_date', 'is_first_email', 'id')

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
    emails = sorted(emails_qs, key=lambda e: page_ids.index(e.id))

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
            'per_page': per_page,
            'sort': sort,
        },
        'page_size_choices': PAGE_SIZE_EMAILS_CHOICES,
    }

    return render(request, 'emails/emais_list.html', context)
