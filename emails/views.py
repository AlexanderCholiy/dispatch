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
from .models import EmailFolder, EmailMessage, EmailReference


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def emails_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()
    folder_name = request.GET.get('folder', '').strip()

    per_page = int(
        request.GET.get('per_page')
        or request.COOKIES.get('per_page_emails')
        or EMAILS_PER_PAGE
    )

    if per_page not in PAGE_SIZE_EMAILS_CHOICES:
        params = request.GET.copy()
        params['per_page'] = EMAILS_PER_PAGE
        return redirect(f"{request.path}?{params.urlencode()}")

    emails = EmailMessage.objects.exclude(
        email_incident__isnull=True
    ).select_related(
        'email_incident',
        'folder',
    ).prefetch_related(
        Prefetch(
            'email_references',
            queryset=EmailReference.objects.select_related(
                'email_msg'
            ).order_by('id'),
            to_attr='prefetched_references'
        ),
        'email_attachments',
        'email_intext_attachments',
        'email_msg_to',
        'email_msg_cc',
    ).order_by('-email_date', 'is_first_email')

    if query:
        filters = (
            Q(email_incident__code__icontains=query)
            | Q(email_subject__icontains=query)
        )
        if query.isdigit():
            filters |= Q(pk=int(query))

        emails = emails.filter(filters).distinct()

    if folder_name:
        emails = emails.filter(folder__name=folder_name)

    folders = cache.get_or_set(
        'email_filter_folders',
        lambda: list(
            EmailFolder.objects.values_list('name', flat=True)
            .distinct()
            .order_by('name')
        ),
        MAX_EMAILS_INFO_CACHE_SEC,
    )

    paginator = Paginator(emails, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    context = {
        'page_obj': page_obj,
        'search_query': query,
        'page_url_base': page_url_base,
        'folders': folders,
        'selected': {
            'folder': folder_name,
            'per_page': per_page,
        },
        'page_size_choices': PAGE_SIZE_EMAILS_CHOICES,
    }
    return render(request, 'emails/emais_list.html', context)
