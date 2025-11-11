import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import render, redirect
from django_ratelimit.decorators import ratelimit
from django.db.models import Q, OuterRef, Subquery, Prefetch
from django.core.cache import cache

from users.utils import role_required
from emails.models import EmailMessage, EmailReference
from .utils import IncidentManager

from .constants import (
    INCIDENTS_PER_PAGE,
    PAGE_SIZE_INCIDENTS_CHOICES,
    MAX_INCIDENTS_INFO_CACHE_SEC
)
from .models import Incident, IncidentStatusHistory, IncidentStatus
from emails.models import EmailMessage
from .forms import MoveEmailsForm


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()
    pole = request.GET.get('pole', '').strip()
    base_station = request.GET.get('base_station', '').strip()
    status_name = request.GET.get('status', '').strip()
    per_page = int(
        request.GET.get('per_page')
        or request.COOKIES.get('per_page')
        or INCIDENTS_PER_PAGE
    )

    if per_page not in PAGE_SIZE_INCIDENTS_CHOICES:
        params = request.GET.copy()
        params['per_page'] = INCIDENTS_PER_PAGE
        return redirect(f"{request.path}?{params.urlencode()}")

    latest_status_subquery = IncidentStatusHistory.objects.filter(
        incident=OuterRef('pk')
    ).order_by('-insert_date')

    first_email_subject_subquery = EmailMessage.objects.filter(
        email_incident=OuterRef('pk')
    ).order_by('email_date', '-is_first_email').values('email_subject')[:1]

    first_email_from_subquery = EmailMessage.objects.filter(
        email_incident=OuterRef('pk')
    ).order_by('-is_first_email', 'email_date').values('email_from')[:1]

    incidents = Incident.objects.all().select_related(
        'incident_type',
        'responsible_user',
        'pole',
        'pole__region',
        'base_station',
    ).prefetch_related(
        'statuses',
        'email_messages',
        'base_station__operator',
    ).annotate(
        latest_status_name=Subquery(
            latest_status_subquery.values('status__name')[:1]
        ),
        latest_status_date=Subquery(
            latest_status_subquery.values('insert_date')[:1]
        ),
        latest_status_class=Subquery(
            latest_status_subquery.values('status__status_type__css_class')[:1]
        ),
        first_email_subject=Subquery(first_email_subject_subquery),
        first_email_from=Subquery(first_email_from_subquery),
    ).order_by('-update_date', '-incident_date', 'id')

    if query:
        incidents = incidents.filter(
            Q(code__icontains=query)
            | Q(email_messages__email_subject__icontains=query)
        ).distinct()

    if pole:
        incidents = incidents.filter(pole__pole__startswith=pole)

    if base_station:
        incidents = incidents.filter(
            base_station__bs_name__startswith=base_station
        )

    if status_name:
        incidents = incidents.filter(latest_status_name=status_name)

    statuses = cache.get_or_set(
        'incident_filter_statuses',
        lambda: list(
            IncidentStatus.objects.values_list('name', flat=True)
            .distinct()
            .order_by('name')
        ),
        MAX_INCIDENTS_INFO_CACHE_SEC,
    )

    paginator = Paginator(incidents, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    context = {
        'page_obj': page_obj,
        'search_query': query,
        'page_url_base': page_url_base,
        'statuses': statuses,
        'selected': {
            'pole': pole,
            'base_station': base_station,
            'status': status_name,
            'per_page': per_page,
        },
        'page_size_choices': PAGE_SIZE_INCIDENTS_CHOICES,
    }
    return render(request, 'incidents/index.html', context)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def incident_detail(request: HttpRequest, incident_id: int) -> HttpResponse:
    incident = (
        Incident.objects
        .select_related(
            'incident_type',
            'responsible_user',
            'pole',
            'pole__region',
            'base_station',
        )
        .prefetch_related(
            'statuses',
            'base_station__operator',
        )
        .filter(pk=incident_id)
        .first()
    )

    if not incident:
        raise Http404('Инцидент не найден')

    sort_order = (
        request.GET.get('email_sort')
        or request.COOKIES.get('per_page')
        or 'asc'
    )
    if sort_order not in ('asc', 'desc'):
        params = request.GET.copy()
        params['email_sort'] = 'asc'
        return redirect(f"{request.path}?{params.urlencode()}")

    sort_reverse = sort_order == 'asc'

    order = ('-email_date', 'is_first_email') if (
        sort_reverse
    ) else ('email_date', '-is_first_email')

    emails = (
        EmailMessage.objects.filter(email_incident=incident)
        .select_related('folder')
        .prefetch_related(
            Prefetch(
                'email_references',
                queryset=(
                    EmailReference.objects
                    .select_related('email_msg')
                    .order_by('id')
                )
            ),
            'email_attachments',
            'email_intext_attachments',
            'email_msg_to',
            'email_msg_cc',
        )
        .order_by(*order)
    )

    if emails.exists():
        first_email = emails.first() if not sort_reverse else emails.last()
        incident.first_email_subject = first_email.email_subject
        incident.first_email_from = first_email.email_from
    else:
        incident.first_email_subject = None
        incident.first_email_from = None

    latest_status = (
        IncidentStatusHistory.objects
        .filter(incident=incident)
        .order_by('-insert_date')
        .select_related('status__status_type')
        .first()
    )

    if latest_status:
        incident.latest_status_name = latest_status.status.name
        incident.latest_status_date = latest_status.insert_date
        incident.latest_status_class = (
            latest_status.status.status_type.css_class
        )
    else:
        incident.latest_status_name = None
        incident.latest_status_date = None
        incident.latest_status_class = None

    email_three = IncidentManager.build_email_tree(emails)

    move_email_form = MoveEmailsForm(
        email_tree=email_three, current_incident=incident
    )
    if request.method == 'POST':
        move_email_form = MoveEmailsForm(
            data=request.POST,
            email_tree=email_three,
            current_incident=incident
        )
        if move_email_form.is_valid():
            target_incident: Incident = (
                move_email_form.cleaned_data['target_incident_code']
            )
            email_ids_groups: list[list[int]] = (
                move_email_form.cleaned_data['email_ids']
            )
            return redirect(
                'incidents:incident_detail', incident_id=target_incident.id
            )
        else:
            for _, errors in move_email_form.errors.items():
                for error in errors:
                    messages.error(request, error)

    context = {
        'incident': incident,
        'email_three': email_three,
        'move_email_form': move_email_form,
    }

    return render(request, 'incidents/incident_detail.html', context)
