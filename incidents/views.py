from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Prefetch, Q, QuerySet, Subquery
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from emails.models import EmailMessage, EmailReference
from users.models import Roles, User
from users.utils import role_required

from .constants import (
    INCIDENTS_PER_PAGE,
    MAX_INCIDENTS_INFO_CACHE_SEC,
    PAGE_SIZE_INCIDENTS_CHOICES
)
from .forms import ConfirmMoveEmailsForm, MoveEmailsForm
from .models import (
    Incident,
    IncidentCategory,
    IncidentHistory,
    IncidentStatus,
    IncidentStatusHistory,
)
from .utils import IncidentManager


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()
    pole = request.GET.get('pole', '').strip()
    base_station = request.GET.get('base_station', '').strip()
    status_name = request.GET.get('status', '').strip()
    category_name = request.GET.get('category', '').strip()
    is_incident_finish = request.GET.get('finish', '').strip()

    if is_incident_finish == 'true':
        is_incident_finish = True
    elif is_incident_finish == 'false':
        is_incident_finish = False
    else:
        is_incident_finish = None

    per_page = int(
        request.GET.get('per_page')
        or request.COOKIES.get('per_page_root')
        or INCIDENTS_PER_PAGE
    )

    if per_page not in PAGE_SIZE_INCIDENTS_CHOICES:
        params = request.GET.copy()
        params['per_page'] = INCIDENTS_PER_PAGE
        return redirect(f'{request.path}?{params.urlencode()}')

    latest_status_subquery = IncidentStatusHistory.objects.filter(
        incident=OuterRef('pk')
    ).order_by('-insert_date')

    first_email_subject_subquery = EmailMessage.objects.filter(
        email_incident=OuterRef('pk')
    ).order_by('email_date', '-is_first_email').values('email_subject')[:1]

    first_email_from_subquery = EmailMessage.objects.filter(
        email_incident=OuterRef('pk')
    ).order_by('-is_first_email', 'email_date').values('email_from')[:1]

    incidents = Incident.objects.exclude(code__isnull=True).select_related(
        'incident_type',
        'responsible_user',
        'pole',
        'pole__region',
        'base_station',
    ).prefetch_related(
        'statuses',
        'email_messages',
        'base_station__operator',
        'categories',
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

    if is_incident_finish is not None:
        incidents = incidents.filter(is_incident_finish=is_incident_finish)

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

    if category_name:
        incidents = incidents.filter(categories__name=category_name)

    statuses = cache.get_or_set(
        'incident_filter_statuses',
        lambda: list(
            IncidentStatus.objects.values_list('name', flat=True)
            .distinct()
            .order_by('name')
        ),
        MAX_INCIDENTS_INFO_CACHE_SEC,
    )

    categories = cache.get_or_set(
        'incident_filter_categories',
        lambda: list(
            IncidentCategory.objects.values_list('name', flat=True)
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
        'categories': categories,
        'selected': {
            'is_incident_finish': is_incident_finish,
            'status': status_name,
            'category': category_name,
            'pole': pole,
            'base_station': base_station,
            'per_page': per_page,
        },
        'page_size_choices': PAGE_SIZE_INCIDENTS_CHOICES,
    }
    return render(request, 'incidents/index.html', context)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def incident_detail(request: HttpRequest, incident_id: int) -> HttpResponse:
    template_name = 'incidents/incident_detail.html'
    incident = IncidentManager().prepare_incident_info(incident_id)

    if not incident:
        raise Http404(f'Инцидент с ID: {incident_id} не найден')

    user: User = request.user
    allowed_roles = [Roles.DISPATCH]
    can_manage = user.role in allowed_roles or user.is_superuser

    if request.method == 'POST':
        if not can_manage:
            roles = [f'"{role.label}"' for role in allowed_roles]
            messages.error(
                request, f'Данная операция доступна только: {', '.join(roles)}'
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )

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

    # Письма отсортированы в запросе к Incident
    emails: QuerySet[EmailMessage] = incident.all_incident_emails

    if emails:
        first_email = emails[-1]
        incident.first_email_subject = first_email.email_subject
        incident.first_email_from = first_email.email_from
    else:
        incident.first_email_subject = None
        incident.first_email_from = None

    email_three = IncidentManager().build_email_tree(emails, sort_reverse)
    move_email_form = MoveEmailsForm(
        email_tree=email_three, current_incident=incident
    )

    confirm_stage = False

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

            target_incident = IncidentManager().prepare_incident_info(
                target_incident.id
            )

            email_ids_groups = move_email_form.cleaned_data['email_ids']

            # Получаем объекты писем для нового дерева:
            email_ids_flat = [i for group in email_ids_groups for i in group]
            new_emails = EmailMessage.objects.filter(
                Q(email_incident=target_incident) | Q(id__in=email_ids_flat)
            ).select_related('folder').prefetch_related(
                Prefetch(
                    'email_references',
                    queryset=(
                        EmailReference.objects
                        .select_related('email_msg')
                        .order_by('id')
                    ),
                    to_attr='prefetched_references'
                ),
                'email_attachments',
                'email_intext_attachments',
                'email_msg_to',
                'email_msg_cc',
            ).order_by('-email_date', 'is_first_email')

            new_email_tree = IncidentManager().build_email_tree(
                new_emails, sort_reverse
            )

            # Письма отсортированы в запросе к Incident
            target_emails: QuerySet[EmailMessage] = (
                target_incident.all_incident_emails
            )

            if target_emails:
                first_email = target_emails[-1]
                incident.first_email_subject = first_email.email_subject
                incident.first_email_from = first_email.email_from
            else:
                incident.first_email_subject = None
                incident.first_email_from = None

            confirm_form = ConfirmMoveEmailsForm(
                data={
                    'source_incident_id': incident.pk,
                    'target_incident_code': target_incident.code,
                    'email_ids': email_ids_groups,
                }
            )

            context = {
                'incident': target_incident,
                'source_incident': incident,
                'email_three': new_email_tree,
                'move_email_form': confirm_form,
                'selected_email_ids': email_ids_groups,
                'confirm_stage': True,
                'can_manage': can_manage,
            }
            return render(request, template_name, context)

        else:
            for _, errors in move_email_form.errors.items():
                for error in errors:
                    messages.error(request, error)

            selected_email_ids = move_email_form.data.get('email_ids', [])
    else:
        selected_email_ids = move_email_form.initial.get('email_ids', [])

    context = {
        'incident': incident,
        'email_three': email_three,
        'move_email_form': move_email_form,
        'selected_email_ids': selected_email_ids,
        'confirm_stage': confirm_stage,
        'can_manage': can_manage,
    }

    return render(request, template_name, context)


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
@require_POST
def confirm_move_emails(request: HttpRequest) -> HttpResponse:
    """Обработка подтверждения переноса писем."""
    form = ConfirmMoveEmailsForm(data=request.POST)

    if not form.is_valid():
        for _, errors in form.errors.items():
            for error in errors:
                messages.error(request, error)
        return redirect(request.META.get('HTTP_REFERER', 'incidents:index'))

    source_incident: Incident = form.cleaned_data['source_incident_id']
    target_incident: Incident = form.cleaned_data['target_incident_code']
    email_ids_groups: list[list[int]] = form.cleaned_data['email_ids']

    if source_incident.code is None or target_incident.code is None:
        messages.error(
            request,
            f'Инцидент {source_incident} и/или {target_incident} не найден.'
        )
        return redirect(request.META.get('HTTP_REFERER', 'incidents:index'))

    email_ids = [email_id for group in email_ids_groups for email_id in group]
    emails_to_move = EmailMessage.objects.filter(
        pk__in=email_ids,
        email_incident=source_incident,
    )

    with transaction.atomic():
        emails_to_move.update(
            email_incident=target_incident, was_added_2_yandex_tracker=False
        )

        source_name = source_incident.code if (
            source_incident.code
        ) else f'ID-{source_incident.pk}'
        target_name = target_incident.code if (
            target_incident.code
        ) else f'ID-{target_incident.pk}'

        IncidentHistory.objects.create(
            incident=source_incident,
            action=(
                f'Письма с ID {", ".join(map(str, email_ids))} '
                f'перенесены в инцидент {target_name}'
            ),
            performed_by=request.user,
        )
        IncidentHistory.objects.create(
            incident=target_incident,
            action=(
                f'Письма с ID {", ".join(map(str, email_ids))} '
                f'добавлены из инцидента {source_name}'
            ),
            performed_by=request.user,
        )

    messages.success(
        request,
        f'Письма успешно перенесены в инцидент {target_incident.code}.'
    )
    return redirect(
        'incidents:incident_detail', incident_id=source_incident.id
    )
