import re
from functools import partial
from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (
    CharField,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
)
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from api.constants import TOTAL_VALID_INCIDENTS_FILTER
from core.constants import CURRENT_TZ, DATETIME_LOCAL_FORMAT
from core.exceptions import (
    ApiBadRequest,
    ApiNotFound,
    ApiServerError,
    ApiTooManyRequests
)
from core.loggers import yt_logger
from core.services.get_max_today_datetime import get_max_today_datetime
from core.threads import tasks_in_threads
from core.utils import humanize_datetime
from core.validators import get_aware_datetime
from emails.email_parser import email_parser
from emails.models import (
    EmailAttachment,
    EmailFolder,
    EmailMessage,
    EmailReference,
    EmailStatus,
    EmailTo,
    EmailToCC
)
from emails.services.clean_email_subject import clean_email_subject
from emails.services.generate_email_msg_id import generate_message_id
from emails.services.get_previous_email_body import get_previous_email_body
from emails.tasks import send_incident_email_task
from monitoring.models import DeviceStatus, DeviceType
from monitoring.services.monitoring_equipment import (
    get_monitiring_cache_equipment,
)
from users.models import Roles, User
from users.utils import role_required
from yandex_tracker.utils import yt_manager

from .annotations import annotate_sla_avr, annotate_sla_dgu, annotate_sla_rvr
from .constants import (
    AVR_CATEGORY,
    DGU_CATEGORY,
    INCIDENTS_PER_PAGE,
    MAX_INCIDENTS_INFO_CACHE_SEC,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFIED_OP_END_STATUS_NAME,
    NOTIFIED_OP_IN_WORK_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_NAME,
    NOTIFY_OP_END_STATUS_NAME,
    NOTIFY_OP_IN_WORK_STATUS_NAME,
    PAGE_SIZE_INCIDENTS_CHOICES,
    RVR_CATEGORY,
)
from .forms import (
    ConfirmMoveEmailsForm,
    IncidentForm,
    MoveEmailsForm,
    NewEmailForm,
)
from .models import (
    Incident,
    IncidentCategory,
    IncidentHistory,
    IncidentStatus,
    IncidentStatusHistory,
    SLAStatus,
    TimeStatus,
)
from .selectors.incidents import IncidentSelector
from .services.get_incident_responsible_users import get_responsible_users
from .services.incident_signature import get_incident_signature
from .services.normalize_incident_subject import normalize_incident_subject
from .utils import IncidentManager
from .validators import (
    validate_notify_avr,
    validate_notify_incident_closed,
    validate_notify_operator,
    validate_notify_rvr,
)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()

    code_pattern = r"^(NT|AVRSERVICE)-\d+$"
    search_only_by_code = (
        True if re.match(code_pattern, query, re.IGNORECASE) else False
    )

    pole = (
        request.GET.get('pole', '').strip()
        or request.COOKIES.get('pole', '').strip()
    ) if not search_only_by_code else None

    base_station = (
        request.GET.get('base_station', '').strip()
        or request.COOKIES.get('base_station', '').strip()
    ) if not search_only_by_code else None

    status_name = (
        request.GET.get('status', '').strip()
        or request.COOKIES.get('status', '').strip()
    ) if not search_only_by_code else None

    category_id = (
        request.GET.get('category') or request.COOKIES.get('category')
    ) if not search_only_by_code else None
    if category_id and category_id.isdigit():
        category_id = int(category_id)
    else:
        category_id = None

    responsible_user_id = (
        request.GET.get('responsible_user')
        or request.COOKIES.get('responsible_user')
    ) if not search_only_by_code else None

    if responsible_user_id and responsible_user_id.isdigit():
        responsible_user_id = int(responsible_user_id)
    elif responsible_user_id == 'none':
        responsible_user_id = responsible_user_id
    else:
        responsible_user_id = None

    is_incident_finish = (
        request.GET.get('finish', '').strip()
        or request.COOKIES.get('finish', '').strip()
    ) if not search_only_by_code else None

    if is_incident_finish == 'true':
        is_incident_finish = True
    elif is_incident_finish == 'false':
        is_incident_finish = False
    else:
        is_incident_finish = None

    was_read = (
        request.GET.get('was_read', '').strip()
        or request.COOKIES.get('was_read', '').strip()
    ) if not search_only_by_code else None

    if was_read == 'true':
        was_read = True
    elif was_read == 'false':
        was_read = False
    else:
        was_read = None

    sla_avr_status = (
        request.GET.get('sla_avr', '').strip()
        or request.COOKIES.get('sla_avr', '').strip()
        or None
    ) if not search_only_by_code else None

    sla_rvr_status = (
        request.GET.get('sla_rvr', '').strip()
        or request.COOKIES.get('sla_rvr', '').strip()
        or None
    ) if not search_only_by_code else None

    sla_dgu_status = (
        request.GET.get('sla_dgu', '').strip()
        or request.COOKIES.get('sla_dgu', '').strip()
        or None
    ) if not search_only_by_code else None

    date_from = (
        request.GET.get('incident_date_from', '').strip()
        or request.COOKIES.get('incident_date_from', '').strip()
        or None
    ) if not search_only_by_code else None
    date_from = get_aware_datetime(date_from)

    date_to = (
        request.GET.get('incident_date_to', '').strip()
        or request.COOKIES.get('incident_date_to', '').strip()
        or None
    ) if not search_only_by_code else None
    date_to = get_aware_datetime(date_to)

    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    sort = (
        request.GET.get('sort_incidents')
        or request.COOKIES.get('sort_incidents')
        or 'desc'
    )

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
    ).order_by('-insert_date', '-id')

    base_qs = (
        Incident.objects
        .filter(TOTAL_VALID_INCIDENTS_FILTER)
        .select_related(
            'incident_type',
            'incident_subtype',
            'responsible_user',
            'pole',
            'pole__region',
            'base_station',
        )
        .prefetch_related('categories')
        .annotate(
            latest_status_name=Subquery(
                latest_status_subquery.values('status__name')[:1]
            ),
        )
    )

    base_qs = annotate_sla_avr(base_qs)
    base_qs = annotate_sla_rvr(base_qs)
    base_qs = annotate_sla_dgu(base_qs)

    if sla_avr_status:
        if sla_avr_status == SLAStatus.EXPIRED.value:
            base_qs = base_qs.filter(sla_avr_expired=True)
        elif sla_avr_status == SLAStatus.WAITING.value:
            base_qs = base_qs.filter(sla_avr_waiting=True)
        elif sla_avr_status == SLAStatus.IN_PROGRESS.value:
            base_qs = base_qs.filter(sla_avr_in_progress=True)
        elif sla_avr_status == SLAStatus.CLOSED_ON_TIME.value:
            base_qs = base_qs.filter(sla_avr_closed_on_time=True)

    if sla_rvr_status:
        if sla_rvr_status == SLAStatus.EXPIRED.value:
            base_qs = base_qs.filter(sla_rvr_expired=True)
        elif sla_rvr_status == SLAStatus.WAITING.value:
            base_qs = base_qs.filter(sla_rvr_waiting=True)
        elif sla_rvr_status == SLAStatus.IN_PROGRESS.value:
            base_qs = base_qs.filter(sla_rvr_in_progress=True)
        elif sla_rvr_status == SLAStatus.CLOSED_ON_TIME.value:
            base_qs = base_qs.filter(sla_rvr_closed_on_time=True)

    if sla_dgu_status:
        if sla_dgu_status == TimeStatus.EXPIRED.value:
            base_qs = base_qs.filter(sla_dgu_expired=True)
        elif sla_dgu_status == TimeStatus.WAITING.value:
            base_qs = base_qs.filter(sla_dgu_waiting=True)
        elif sla_dgu_status == TimeStatus.IN_PROGRESS.value:
            base_qs = base_qs.filter(sla_dgu_in_progress=True)
        elif sla_dgu_status == TimeStatus.CLOSED_ON_TIME.value:
            base_qs = base_qs.filter(sla_dgu_closed_on_time=True)

    if is_incident_finish is not None:
        base_qs = base_qs.filter(is_incident_finish=is_incident_finish)

    if was_read is not None:
        base_qs = base_qs.filter(was_read=was_read)

    if query:
        base_qs = base_qs.filter(
            Q(code__icontains=query)
            | Q(email_messages__email_subject__icontains=query)
        ).distinct()

    if pole:
        base_qs = base_qs.filter(pole__pole__startswith=pole)

    if base_station:
        base_qs = base_qs.filter(
            base_station__bs_name__startswith=base_station
        )

    if date_from:
        base_qs = base_qs.filter(incident_date__gte=date_from)

    if date_to:
        base_qs = base_qs.filter(incident_date__lte=date_to)

    if status_name:
        base_qs = base_qs.filter(latest_status_name=status_name)

    if category_id:
        base_qs = base_qs.filter(categories__id=category_id)

    if responsible_user_id == 'none':
        base_qs = base_qs.filter(responsible_user__isnull=True)
    elif responsible_user_id:
        base_qs = base_qs.filter(responsible_user__id=responsible_user_id)

    if sort == 'asc':
        base_qs = base_qs.order_by('incident_date', 'update_date', 'id')
    else:
        base_qs = base_qs.order_by('-incident_date', '-update_date', 'id')

    paginator = Paginator(base_qs.values_list('id', flat=True), per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_ids = list(page_obj.object_list)

    first_email_subquery = (
        EmailMessage.objects
        .filter(email_incident=OuterRef('pk'))
        .order_by(
            '-is_first_email',
            'email_date',
        )
    )

    incidents_qs = Incident.objects.filter(id__in=page_ids).select_related(
        'incident_type',
        'incident_subtype',
        'responsible_user',
        'pole',
        'pole__region',
        'base_station',
    ).prefetch_related('categories').annotate(
        latest_status_name=Subquery(
            latest_status_subquery.values('status__name')[:1]
        ),
        latest_status_date=Subquery(
            latest_status_subquery.values('insert_date')[:1]
        ),
        latest_status_class=Subquery(
            latest_status_subquery.values('status__status_type__css_class')[:1]
        ),
        first_email_subject=Subquery(
            first_email_subquery.values('email_subject')[:1]
        ),
        first_email_from=Subquery(
            first_email_subquery.values('email_from')[:1]
        ),
        sla_avr_status_val=Value('', output_field=CharField()),
        sla_rvr_status_val=Value('', output_field=CharField()),
        sla_dgu_status_val=Value('', output_field=CharField()),
    )

    id_index = {id_: i for i, id_ in enumerate(page_ids)}
    incidents = sorted(incidents_qs, key=lambda n: id_index[n.id])

    for incident in incidents:
        incident.sla_avr_status_val = incident.sla_avr_status
        incident.sla_rvr_status_val = incident.sla_rvr_status
        incident.sla_dgu_status_val = incident.sla_dgu_status

        incident.updated_human = humanize_datetime(incident.update_date)

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
            IncidentCategory.objects.all().order_by('name')
            .values('id', 'name')
        ),
        MAX_INCIDENTS_INFO_CACHE_SEC,
    )

    responsible_users = get_responsible_users()

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    allowed_roles = [Roles.DISPATCH]
    can_manage = (
        request.user.role in allowed_roles or request.user.is_superuser
    )

    context = {
        'page_obj': page_obj,
        'incidents': incidents,
        'search_query': query,
        'page_url_base': page_url_base,
        'statuses': statuses,
        'categories': categories,
        'responsible_users': responsible_users,
        'sla_statuses': SLAStatus,
        'time_statuses': TimeStatus,
        'selected': {
            'is_incident_finish': is_incident_finish,
            'was_read': was_read,
            'status': status_name,
            'category': category_id,
            'responsible_user': responsible_user_id,
            'pole': pole,
            'base_station': base_station,
            'per_page': per_page,
            'sort': sort,
            'sla_avr_status': sla_avr_status,
            'sla_rvr_status': sla_rvr_status,
            'sla_dgu_status': sla_dgu_status,
            'date_from': (
                date_from.strftime(DATETIME_LOCAL_FORMAT) if date_from else ''
            ),
            'date_to': (
                date_to.strftime(DATETIME_LOCAL_FORMAT) if date_to else ''
            ),
        },
        'page_size_choices': PAGE_SIZE_INCIDENTS_CHOICES,
        'can_manage': can_manage,
        'max_datetime': get_max_today_datetime(),
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

    monitiring_equipment = (
        get_monitiring_cache_equipment(incident.pole.pole)
        if incident.pole else None
    ) or []

    monitoring_data = {
        eq['modem_ip']: {
            **eq,
            'level_val': DeviceType(eq['level']).label,
            'status_val': DeviceStatus(eq['status']).label,
        }
        for eq in monitiring_equipment
    }

    sorted_monitoring = sorted(
        monitoring_data.items(),
        key=lambda item: (item[1]['level_val'], item[0])
    )

    user: User = request.user
    allowed_roles = [Roles.DISPATCH]
    can_manage = user.role in allowed_roles or user.is_superuser

    incident_form = IncidentForm(
        instance=incident,
        can_edit=can_manage,
        author=user,
    )

    if request.method == 'POST':
        if not can_manage:
            roles = [f'"{role.label}"' for role in allowed_roles]
            messages.error(
                request, f'Данная операция доступна только: {', '.join(roles)}'
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )
        elif incident.is_yt_tracker_controlled:
            messages.error(
                request,
                (
                    'Управление этим инцидентом происходит из интерфейса '
                    'YandexTracker'
                )
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )

    if request.method == 'POST' and 'incident_submit' in request.POST:
        incident_form = IncidentForm(
            data=request.POST,
            instance=incident,
            can_edit=can_manage,
            author=user,
        )
        if incident_form.is_valid():
            incident_form.save()
            messages.success(request, 'Данные обновлены')
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )
        else:
            messages.warning(
                request, 'Пожалуйста, исправьте ошибки в формах'
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

    if request.method == 'POST' and 'move_emails_submit' in request.POST:
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
                'incident_form': incident_form,
                'monitoring': sorted_monitoring,
                'active_tab': 'email',
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
        'incident_form': incident_form,
        'monitoring': sorted_monitoring,
        'active_tab': 'incident',
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
            f'Инцидент {source_incident} и/или {target_incident} не найден'
        )
        return redirect(request.META.get('HTTP_REFERER', 'incidents:index'))

    email_ids = [email_id for group in email_ids_groups for email_id in group]

    # Дополнительные параметры запроса нужны для YandexTracker:
    emails_to_move = EmailMessage.objects.filter(
        pk__in=email_ids,
        email_incident=source_incident,
    ).order_by('id')

    old_emails = list(emails_to_move)

    with transaction.atomic():
        emails_to_move.update(
            email_incident=target_incident,
            need_2_add_in_yandex_tracker=True,
            was_added_2_yandex_tracker=False,  # Надо для трекера
        )

        last_email = EmailMessage.objects.filter(
            email_incident=source_incident,
            is_email_from_yandex_tracker=False,
            was_added_2_yandex_tracker=True,
        ).exclude(pk__in=email_ids).order_by('-email_date').first()

        if last_email:
            last_email.need_2_add_in_yandex_tracker = True
            last_email.was_added_2_yandex_tracker = False
            last_email.save()

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

        try:
            if source_incident.is_yt_tracker_controlled:
                yt_comments = yt_manager.select_issue_comments(
                    source_incident.code
                )
            else:
                yt_comments = []

            tasks = []

            for comment in yt_comments:
                comment_id: int = comment['id']

                for email in old_emails:
                    if yt_manager.is_comment_related(comment, email):
                        tasks.append(
                            partial(
                                yt_manager.delete_comment,
                                source_incident.code,
                                comment_id,
                            )
                        )
                        break

            tasks_in_threads(
                tasks, yt_logger, cpu_bound=False, raise_exs=True
            )

        except (ApiNotFound, ApiBadRequest):
            transaction.set_rollback(True)
            messages.error(
                request,
                'В YandexTracker не найден инцидент с кодом: '
                f'{source_incident.code}'
            )
        except (ApiTooManyRequests, ApiServerError):
            transaction.set_rollback(True)
            messages.warning(
                request,
                'YandexTracker временно не доступен. Попробуйте позже.'
            )
        else:
            if target_incident.is_yt_tracker_controlled:
                messages.success(
                    request,
                    'Письма успешно перенесены. '
                    'В ближайшее время они появятся в YandexTracker как '
                    f'комментарии к задаче {target_incident.code}.'
                )
            else:
                messages.success(request, 'Письма успешно перенесены.')

    return redirect(
        'incidents:incident_detail', incident_id=source_incident.id
    )


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def create_incident(request: HttpRequest) -> HttpResponse:
    template_name = 'incidents/create_incident.html'

    user: User = request.user

    if request.method == 'POST':
        form = IncidentForm(
            data=request.POST,
            can_edit=True,
            author=user,
        )

        if form.is_valid():
            incident: Incident = form.save()
            incident.is_yt_tracker_controlled = False
            incident.save()
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )

    else:
        form = IncidentForm(
            initial={
                'responsible_user': request.user
            },
            can_edit=True,
            author=user,
        )

    context = {
        'form': form,
        'active_tab': 'incident',
    }

    return render(request, template_name, context)


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def new_email(
    request: HttpRequest,
    incident_id: int,
    reply_email_id: Optional[int] = None
) -> HttpResponse:
    template_name = 'emails/new_email.html'
    incident = IncidentSelector.incidents_with_email_history(incident_id)

    emails = incident.all_incident_emails

    first_email: Optional[EmailMessage] = emails[0] if emails else None

    reply_to_email: Optional[EmailMessage] = None
    if reply_email_id is not None:
        reply_to_email = next(
            (e for e in emails if e.id == reply_email_id),
            None
        )
        if not reply_to_email:
            raise Http404

    previous_plain = None
    previous_html = None

    if reply_to_email is not None:
        previous_plain, previous_html = get_previous_email_body(reply_to_email)

    if request.method == 'POST':
        form = NewEmailForm(request.POST, request.FILES)

        if form.is_valid():
            now = timezone.now()
            message_id = generate_message_id()

            raw_subject = form.cleaned_data.get('subject') or ''

            subject = normalize_incident_subject(
                raw_subject,
                incident.code
            )

            with transaction.atomic():
                folder = EmailFolder.objects.get(name='SENT')

                email_msg = EmailMessage.objects.create(
                    email_msg_id=message_id,
                    email_subject=subject,
                    email_from=email_parser.email_login,
                    email_date=now,
                    email_body=form.cleaned_data.get('body'),
                    is_first_email=not first_email,
                    is_email_from_yandex_tracker=False,
                    was_added_2_yandex_tracker=False,
                    need_2_add_in_yandex_tracker=True,
                    email_incident=incident,
                    folder=folder,
                    status=EmailStatus.PENDING,
                    email_msg_reply_id=(
                        reply_to_email.email_msg_id
                        if reply_to_email else None
                    ),
                )

                if reply_to_email:
                    # Копируем все references исходного письма:
                    for ref in reply_to_email.prefetched_references:
                        EmailReference.objects.create(
                            email_msg=email_msg,
                            email_msg_references=ref.email_msg_references
                        )

                    # Добавляем само письмо, на которое отвечаем:
                    EmailReference.objects.create(
                        email_msg=email_msg,
                        email_msg_references=reply_to_email.email_msg_id
                    )

                for email in form.cleaned_data.get('to', []):
                    EmailTo.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                for email in form.cleaned_data.get('cc', []):
                    EmailToCC.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                files = form.cleaned_data.get('attachments')

                if files:
                    for f in files:
                        EmailAttachment.objects.create(
                            email_msg=email_msg,
                            file_url=f
                        )

                transaction.on_commit(
                    lambda: send_incident_email_task.delay(email_msg.id)
                )

            messages.success(
                request,
                (
                    f'Письмо (ID: {email_msg.id}) готовится к отправке и '
                    'скоро будет доставлено.'
                )
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )
    else:
        initial_data = {}

        if (
            reply_to_email is None
            and first_email
            and first_email.email_subject
        ):
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = clean_subj

        elif reply_to_email is not None:
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = f'Re: {clean_subj}'

            email_to = [
                obj.email_to for obj in reply_to_email.prefetched_to
                if obj.email_to != email_parser.email_login
            ]
            if reply_to_email.email_from != email_parser.email_login:
                email_to.append(reply_to_email.email_from)

            initial_data['to'] = ', '.join(email_to)
            initial_data['cc'] = ', '.join([
                obj.email_to for obj in reply_to_email.prefetched_cc
                if obj.email_to != email_parser.email_login
            ])

        initial_data['body'] = get_incident_signature(incident)

        form = NewEmailForm(initial=initial_data)

    context = {
        'incident': incident,
        'form': form,
        'first_email': first_email,
        'reply_to_email': reply_to_email,
        'previous_plain': previous_plain,
        'previous_html': previous_html,
        'active_tab': 'email',
    }

    return render(request, template_name, context)


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notify_operator(request: HttpRequest, incident_id: int) -> HttpResponse:
    template_name = 'emails/new_email.html'
    incident = IncidentSelector.incidents_with_email_history(incident_id)

    last_status: Optional[IncidentStatus] = (
        incident.prefetched_status_history[0].status
        if incident.prefetched_status_history
        else None
    )

    error_message = validate_notify_operator(
        incident,
        last_status,
    )

    if error_message:
        messages.error(request, error_message)
        return redirect('incidents:incident_detail', incident_id=incident.id)

    emails = incident.all_incident_emails

    first_email: Optional[EmailMessage] = emails[0] if emails else None

    reply_to_email = first_email

    previous_plain, previous_html = None, None

    if reply_to_email:
        previous_plain, previous_html = get_previous_email_body(reply_to_email)

    if request.method == 'POST':
        form = NewEmailForm(request.POST, request.FILES)

        if form.is_valid():
            now = timezone.now()
            message_id = generate_message_id()

            raw_subject = form.cleaned_data.get('subject') or ''

            subject = normalize_incident_subject(
                raw_subject,
                incident.code
            )

            with transaction.atomic():
                folder = EmailFolder.objects.get(name='SENT')

                email_msg = EmailMessage.objects.create(
                    email_msg_id=message_id,
                    email_subject=subject,
                    email_from=email_parser.email_login,
                    email_date=now,
                    email_body=form.cleaned_data.get('body'),
                    is_first_email=not first_email,
                    is_email_from_yandex_tracker=False,
                    was_added_2_yandex_tracker=False,
                    need_2_add_in_yandex_tracker=True,
                    email_incident=incident,
                    folder=folder,
                    status=EmailStatus.PENDING,
                    email_msg_reply_id=(
                        reply_to_email.email_msg_id
                        if reply_to_email else None
                    ),
                )

                if reply_to_email:
                    # Копируем все references исходного письма:
                    for ref in reply_to_email.prefetched_references:
                        EmailReference.objects.create(
                            email_msg=email_msg,
                            email_msg_references=ref.email_msg_references
                        )

                    # Добавляем само письмо, на которое отвечаем:
                    EmailReference.objects.create(
                        email_msg=email_msg,
                        email_msg_references=reply_to_email.email_msg_id
                    )

                for email in form.cleaned_data.get('to', []):
                    EmailTo.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                for email in form.cleaned_data.get('cc', []):
                    EmailToCC.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                files = form.cleaned_data.get('attachments')

                if files:
                    for f in files:
                        EmailAttachment.objects.create(
                            email_msg=email_msg,
                            file_url=f
                        )

                new_status, _ = (
                    IncidentStatus.objects
                    .get_or_create(name=NOTIFY_OP_IN_WORK_STATUS_NAME)
                )

                category_names = {
                    c.name for c in incident.categories.all()
                }
                comments = (
                    'Статус добавлен автоматически после '
                    'начала отправки автоответа.'
                )

                IncidentStatusHistory.objects.create(
                    incident=incident,
                    status=new_status,
                    comments=comments,
                    is_avr_category=AVR_CATEGORY in category_names,
                    is_rvr_category=RVR_CATEGORY in category_names,
                    is_dgu_category=DGU_CATEGORY in category_names,
                )
                incident.statuses.add(new_status)

                transaction.on_commit(
                    lambda: send_incident_email_task.delay(
                        email_msg.id,
                        new_status_name=NOTIFIED_OP_IN_WORK_STATUS_NAME,
                    )
                )

            messages.success(
                request,
                (
                    f'Письмо (ID: {email_msg.id}) готовится к отправке и '
                    'скоро будет доставлено заявителю.'
                )
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )
    else:
        initial_data = {}

        if (
            reply_to_email is None
            and first_email
            and first_email.email_subject
        ):
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = clean_subj

        elif reply_to_email is not None:
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = f'Re: {clean_subj}'

            email_to = [
                obj.email_to for obj in reply_to_email.prefetched_to
                if obj.email_to != email_parser.email_login
            ]
            if reply_to_email.email_from != email_parser.email_login:
                email_to.append(reply_to_email.email_from)

            initial_data['to'] = ', '.join(email_to)
            initial_data['cc'] = ', '.join(
                [
                    obj.email_to for obj in reply_to_email.prefetched_cc
                    if obj.email_to != email_parser.email_login
                ]
            )

        incident_label = f'{incident.code} ' if incident.code else ''

        signature = get_incident_signature(incident)

        initial_data['body'] = (
            f'Заявка {incident_label} принята в работу.'
            f'{signature}'
        )

        form = NewEmailForm(initial=initial_data)

    context = {
        'incident': incident,
        'form': form,
        'first_email': first_email,
        'previous_plain': previous_plain,
        'previous_html': previous_html,
        'email_header': 'Уведомление оператору о принятии в работу инцидента',
        'active_tab': 'email',
    }

    return render(request, template_name, context)


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notify_avr_contractor(
    request: HttpRequest, incident_id: int
) -> HttpResponse:
    template_name = 'emails/new_email.html'
    incident = IncidentSelector.incidents_with_email_history(incident_id)

    last_status: Optional[IncidentStatus] = (
        incident.prefetched_status_history[0].status
        if incident.prefetched_status_history
        else None
    )

    category_names = {
        c.name for c in incident.categories.all()
    }

    error_message = validate_notify_avr(
        incident,
        last_status,
        category_names,
    )

    if error_message:
        messages.error(request, error_message)
        return redirect('incidents:incident_detail', incident_id=incident.id)

    first_email: Optional[EmailMessage] = (
        incident.all_incident_emails[0]
        if incident.all_incident_emails else None
    )

    previous_plain = None
    previous_html = None

    if request.method == 'POST':
        form = NewEmailForm(request.POST, request.FILES)

        if form.is_valid():
            now = timezone.now()
            message_id = generate_message_id()

            raw_subject = form.cleaned_data.get('subject') or ''

            subject = normalize_incident_subject(
                raw_subject,
                incident.code
            )

            with transaction.atomic():
                folder = EmailFolder.objects.get(name='SENT')

                email_msg = EmailMessage.objects.create(
                    email_msg_id=message_id,
                    email_subject=subject,
                    email_from=email_parser.email_login,
                    email_date=now,
                    email_body=form.cleaned_data.get('body'),
                    is_first_email=not first_email,
                    is_email_from_yandex_tracker=False,
                    was_added_2_yandex_tracker=False,
                    need_2_add_in_yandex_tracker=True,
                    email_incident=incident,
                    folder=folder,
                    status=EmailStatus.PENDING,
                    email_msg_reply_id=None,
                )

                for email in form.cleaned_data.get('to', []):
                    EmailTo.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                for email in form.cleaned_data.get('cc', []):
                    EmailToCC.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                files = form.cleaned_data.get('attachments')

                if files:
                    for f in files:
                        EmailAttachment.objects.create(
                            email_msg=email_msg,
                            file_url=f
                        )

                new_status, _ = (
                    IncidentStatus.objects
                    .get_or_create(name=NOTIFY_CONTRACTOR_STATUS_NAME)
                )

                comments = (
                    'Статус добавлен автоматически после '
                    'начала отправки автоответа.'
                )

                IncidentStatusHistory.objects.create(
                    incident=incident,
                    status=new_status,
                    comments=comments,
                    is_avr_category=AVR_CATEGORY in category_names,
                    is_rvr_category=RVR_CATEGORY in category_names,
                    is_dgu_category=DGU_CATEGORY in category_names,
                )
                incident.statuses.add(new_status)

                transaction.on_commit(
                    lambda: send_incident_email_task.delay(
                        email_msg.id,
                        new_status_name=NOTIFIED_CONTRACTOR_STATUS_NAME,
                    )
                )

                now = timezone.now()
                incident.avr_start_date = incident.avr_start_date or now
                incident.save()

            messages.success(
                request,
                (
                    f'Письмо (ID: {email_msg.id}) готовится к отправке и '
                    'скоро будет доставлено подрядчику по АВР.'
                )
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )
    else:
        initial_data = {}

        if (
            first_email
            and first_email.email_subject
        ):
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = clean_subj

        avr_emails = [
            obj.email.email
            for obj in incident.pole.prefetched_pole_avr_emails
        ]

        initial_data['to'] = ', '.join(avr_emails)

        text_parts = []

        incident_label = f'{incident.code} ' if incident.code else ''

        text_parts.append(
            f'На вас назначен инцидент {incident_label} (АВР).'
        )

        pole = incident.pole

        pole_region = (
            pole.region.region_ru or pole.region.region_en
        ) if pole.region else None

        text_parts.append('\nИНФОРМАЦИЯ ОБ ОПОРЕ:')
        text_parts.append(f'  • Шифр опоры: {pole.pole}')

        if pole_region:
            text_parts.append(f'  • Регион: {pole_region}')

        if pole.address:
            text_parts.append(f'  • Адрес: {pole.address}')

        if pole.pole_latitude and pole.pole_longtitude:
            text_parts.append(
                f'  • Координаты: {pole.pole_latitude}, {pole.pole_longtitude}'
            )

        if incident.base_station:
            bs = incident.base_station

            text_parts.append('\nИНФОРМАЦИЯ О БАЗОВОЙ СТАНЦИИ:')
            text_parts.append(f'  • Номер БС: {bs.bs_name}')

            if hasattr(bs, 'prefetched_operators'):
                operators = [
                    op.operator_name
                    for op in bs.prefetched_operators
                ]
            else:
                operators = list(
                    bs.operator.values_list('operator_name', flat=True)
                )

            if operators:
                text_parts.append(f'  • Операторы: {", ".join(operators)}')

        text_parts.append('\nДЕТАЛИ ИНЦИДЕНТА:')

        incident_date = (
            incident.incident_date
            .astimezone(CURRENT_TZ)
            .strftime('%d.%m.%Y %H:%M (МСК)')
        )

        text_parts.append(f'  • Дата регистрации: {incident_date}')

        if incident.incident_type:
            text_parts.append(
                f'  • Тип инцидента: {incident.incident_type.name}'
            )
            if incident.incident_type.description:
                text_parts.append(
                    f'  • Описание: {incident.incident_type.description}'
                )

        now = timezone.now()
        incident.avr_start_date = incident.avr_start_date or now

        if incident.sla_avr_deadline:
            sla_deadline = (
                incident.sla_avr_deadline
                .astimezone(CURRENT_TZ)
                .strftime('%d.%m.%Y %H:%M (МСК)')
            )
            text_parts.append(f'  • SLA дедлайн: {sla_deadline}')

        signature = get_incident_signature(incident, True)

        text_parts.append(signature)

        if first_email:
            first_email_plain, _ = get_previous_email_body(first_email)
            if first_email_plain:
                text_parts.append(first_email_plain)

        initial_data['body'] = '\n'.join(text_parts)

        form = NewEmailForm(initial=initial_data)

    context = {
        'incident': incident,
        'form': form,
        'first_email': first_email,
        'previous_plain': previous_plain,
        'previous_html': previous_html,
        'email_header': (
            'Уведомление подрядчику по АВР о передаче инцидента'
        ),
        'active_tab': 'email',
    }

    return render(request, template_name, context)


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notify_rvr_contractor(
    request: HttpRequest, incident_id: int
) -> HttpResponse:
    template_name = 'emails/new_email.html'
    incident = IncidentSelector.incidents_with_email_history(incident_id)

    last_status: Optional[IncidentStatus] = (
        incident.prefetched_status_history[0].status
        if incident.prefetched_status_history
        else None
    )

    category_names = {
        c.name for c in incident.categories.all()
    }

    error_message = validate_notify_rvr(
        incident,
        last_status,
        category_names,
    )

    if error_message:
        messages.error(request, error_message)
        return redirect('incidents:incident_detail', incident_id=incident.id)

    first_email: Optional[EmailMessage] = (
        incident.all_incident_emails[0]
        if incident.all_incident_emails else None
    )

    previous_plain = None
    previous_html = None

    if request.method == 'POST':
        form = NewEmailForm(request.POST, request.FILES)

        if form.is_valid():
            now = timezone.now()
            message_id = generate_message_id()

            raw_subject = form.cleaned_data.get('subject') or ''

            subject = normalize_incident_subject(
                raw_subject,
                incident.code
            )

            with transaction.atomic():
                folder = EmailFolder.objects.get(name='SENT')

                email_msg = EmailMessage.objects.create(
                    email_msg_id=message_id,
                    email_subject=subject,
                    email_from=email_parser.email_login,
                    email_date=now,
                    email_body=form.cleaned_data.get('body'),
                    is_first_email=not first_email,
                    is_email_from_yandex_tracker=False,
                    was_added_2_yandex_tracker=False,
                    need_2_add_in_yandex_tracker=True,
                    email_incident=incident,
                    folder=folder,
                    status=EmailStatus.PENDING,
                    email_msg_reply_id=None,
                )

                for email in form.cleaned_data.get('to', []):
                    EmailTo.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                for email in form.cleaned_data.get('cc', []):
                    EmailToCC.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                files = form.cleaned_data.get('attachments')

                if files:
                    for f in files:
                        EmailAttachment.objects.create(
                            email_msg=email_msg,
                            file_url=f
                        )

                new_status, _ = (
                    IncidentStatus.objects
                    .get_or_create(name=NOTIFY_CONTRACTOR_STATUS_NAME)
                )

                comments = (
                    'Статус добавлен автоматически после '
                    'начала отправки автоответа.'
                )

                IncidentStatusHistory.objects.create(
                    incident=incident,
                    status=new_status,
                    comments=comments,
                    is_avr_category=AVR_CATEGORY in category_names,
                    is_rvr_category=RVR_CATEGORY in category_names,
                    is_dgu_category=DGU_CATEGORY in category_names,
                )
                incident.statuses.add(new_status)

                transaction.on_commit(
                    lambda: send_incident_email_task.delay(
                        email_msg.id,
                        new_status_name=NOTIFIED_CONTRACTOR_STATUS_NAME,
                    )
                )

                now = timezone.now()
                incident.rvr_start_date = incident.rvr_start_date or now
                incident.save()

            messages.success(
                request,
                (
                    f'Письмо (ID: {email_msg.id}) готовится к отправке и '
                    'скоро будет доставлено подрядчику по РВР.'
                )
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )
    else:
        initial_data = {}

        if (
            first_email
            and first_email.email_subject
        ):
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = clean_subj

        if (
            incident.pole
            and incident.pole.region
            and incident.pole.region.rvr_email
        ):
            initial_data['to'] = incident.pole.region.rvr_email

        text_parts = []

        incident_label = f'{incident.code} ' if incident.code else ''

        text_parts.append(
            f'На вас назначен инцидент {incident_label} (РВР).'
        )

        pole = incident.pole

        pole_region = (
            pole.region.region_ru or pole.region.region_en
        ) if pole.region else None

        text_parts.append('\nИНФОРМАЦИЯ ОБ ОПОРЕ:')
        text_parts.append(f'  • Шифр опоры: {pole.pole}')

        if pole_region:
            text_parts.append(f'  • Регион: {pole_region}')

        if pole.address:
            text_parts.append(f'  • Адрес: {pole.address}')

        if pole.pole_latitude and pole.pole_longtitude:
            text_parts.append(
                f'  • Координаты: {pole.pole_latitude}, {pole.pole_longtitude}'
            )

        if incident.base_station:
            bs = incident.base_station

            text_parts.append('\nИНФОРМАЦИЯ О БАЗОВОЙ СТАНЦИИ:')
            text_parts.append(f'  • Номер БС: {bs.bs_name}')

            if hasattr(bs, 'prefetched_operators'):
                operators = [
                    op.operator_name
                    for op in bs.prefetched_operators
                ]
            else:
                operators = list(
                    bs.operator.values_list('operator_name', flat=True)
                )

            if operators:
                text_parts.append(f'  • Операторы: {", ".join(operators)}')

        text_parts.append('\nДЕТАЛИ ИНЦИДЕНТА:')

        incident_date = (
            incident.incident_date
            .astimezone(CURRENT_TZ)
            .strftime('%d.%m.%Y %H:%M (МСК)')
        )

        text_parts.append(f'  • Дата регистрации: {incident_date}')

        if incident.incident_type:
            text_parts.append(
                f'  • Тип инцидента: {incident.incident_type.name}'
            )
            if incident.incident_type.description:
                text_parts.append(
                    f'  • Описание: {incident.incident_type.description}'
                )

        now = timezone.now()
        incident.rvr_start_date = incident.rvr_start_date or now

        if incident.sla_rvr_deadline:
            sla_deadline = (
                incident.sla_rvr_deadline
                .astimezone(CURRENT_TZ)
                .strftime('%d.%m.%Y %H:%M (МСК)')
            )
            text_parts.append(f'  • SLA дедлайн: {sla_deadline}')

        signature = get_incident_signature(incident, True)

        text_parts.append(signature)

        if first_email:
            first_email_plain, _ = get_previous_email_body(first_email)
            if first_email_plain:
                text_parts.append(first_email_plain)

        initial_data['body'] = '\n'.join(text_parts)

        form = NewEmailForm(initial=initial_data)

    context = {
        'incident': incident,
        'form': form,
        'first_email': first_email,
        'previous_plain': previous_plain,
        'previous_html': previous_html,
        'email_header': (
            'Уведомление подрядчику по РВР о передаче инцидента'
        ),
        'active_tab': 'email',
    }

    return render(request, template_name, context)


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notify_incident_closed(
    request: HttpRequest, incident_id: int
) -> HttpResponse:
    template_name = 'emails/new_email.html'
    incident = IncidentSelector.incidents_with_email_history(incident_id)

    last_status: Optional[IncidentStatus] = (
        incident.prefetched_status_history[0].status
        if incident.prefetched_status_history
        else None
    )

    error_message = validate_notify_incident_closed(
        incident,
        last_status,
    )

    if error_message:
        messages.error(request, error_message)
        return redirect('incidents:incident_detail', incident_id=incident.id)

    first_email: Optional[EmailMessage] = (
        incident.all_incident_emails[0]
        if incident.all_incident_emails else None
    )
    reply_to_email = first_email

    previous_plain, previous_html = None, None
    if reply_to_email:
        previous_plain, previous_html = get_previous_email_body(reply_to_email)

    if request.method == 'POST':
        form = NewEmailForm(request.POST, request.FILES)

        if form.is_valid():
            now = timezone.now()
            message_id = generate_message_id()

            raw_subject = form.cleaned_data.get('subject') or ''

            subject = normalize_incident_subject(
                raw_subject,
                incident.code
            )

            with transaction.atomic():
                folder = EmailFolder.objects.get(name='SENT')

                email_msg = EmailMessage.objects.create(
                    email_msg_id=message_id,
                    email_subject=subject,
                    email_from=email_parser.email_login,
                    email_date=now,
                    email_body=form.cleaned_data.get('body'),
                    is_first_email=not first_email,
                    is_email_from_yandex_tracker=False,
                    was_added_2_yandex_tracker=False,
                    need_2_add_in_yandex_tracker=True,
                    email_incident=incident,
                    folder=folder,
                    status=EmailStatus.PENDING,
                    email_msg_reply_id=(
                        reply_to_email.email_msg_id
                        if reply_to_email else None
                    ),
                )

                if reply_to_email:
                    # Копируем все references исходного письма:
                    for ref in reply_to_email.prefetched_references:
                        EmailReference.objects.create(
                            email_msg=email_msg,
                            email_msg_references=ref.email_msg_references
                        )

                    # Добавляем само письмо, на которое отвечаем:
                    EmailReference.objects.create(
                        email_msg=email_msg,
                        email_msg_references=reply_to_email.email_msg_id
                    )

                for email in form.cleaned_data.get('to', []):
                    EmailTo.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                for email in form.cleaned_data.get('cc', []):
                    EmailToCC.objects.create(
                        email_msg=email_msg,
                        email_to=email
                    )

                files = form.cleaned_data.get('attachments')

                if files:
                    for f in files:
                        EmailAttachment.objects.create(
                            email_msg=email_msg,
                            file_url=f
                        )

                new_status, _ = (
                    IncidentStatus.objects
                    .get_or_create(name=NOTIFY_OP_END_STATUS_NAME)
                )

                category_names = {
                    c.name for c in incident.categories.all()
                }
                comments = (
                    'Статус добавлен автоматически после '
                    'начала отправки автоответа.'
                )

                IncidentStatusHistory.objects.create(
                    incident=incident,
                    status=new_status,
                    comments=comments,
                    is_avr_category=AVR_CATEGORY in category_names,
                    is_rvr_category=RVR_CATEGORY in category_names,
                    is_dgu_category=DGU_CATEGORY in category_names,
                )
                incident.statuses.add(new_status)

                transaction.on_commit(
                    lambda: send_incident_email_task.delay(
                        email_msg.id,
                        new_status_name=NOTIFIED_OP_END_STATUS_NAME,
                    )
                )

                now = timezone.now()
                if AVR_CATEGORY in category_names:
                    incident.avr_end_date = (
                        now
                        if (
                            incident.avr_start_date
                            and not incident.avr_end_date
                        )
                        else incident.avr_end_date
                    )
                if RVR_CATEGORY in category_names:
                    incident.rvr_end_date = (
                        now
                        if (
                            incident.rvr_start_date
                            and not incident.rvr_end_date
                        )
                        else incident.rvr_end_date
                    )

                incident.save()

            messages.success(
                request,
                (
                    f'Письмо (ID: {email_msg.id}) готовится к отправке и '
                    'скоро будет доставлено заявителю.'
                )
            )
            return redirect(
                'incidents:incident_detail', incident_id=incident.id
            )
    else:
        initial_data = {}

        if (
            reply_to_email is None
            and first_email
            and first_email.email_subject
        ):
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = clean_subj

        elif reply_to_email is not None:
            clean_subj = clean_email_subject(
                first_email.email_subject or '', incident.code
            )
            initial_data['subject'] = f'Re: {clean_subj}'

            email_to = [
                obj.email_to for obj in reply_to_email.prefetched_to
                if obj.email_to != email_parser.email_login
            ]
            if reply_to_email.email_from != email_parser.email_login:
                email_to.append(reply_to_email.email_from)

            initial_data['to'] = ', '.join(email_to)
            initial_data['cc'] = ', '.join(
                [
                    obj.email_to for obj in reply_to_email.prefetched_cc
                    if obj.email_to != email_parser.email_login
                ]
            )

        incident_label = f'{incident.code} ' if incident.code else ''

        signature = get_incident_signature(incident)

        initial_data['body'] = (
            f'Инцидент {incident_label}устранён.'
            '\n\nПросим проверить и подтвердить. '
            'Если в течение 12 часов обратная связь не поступит, '
            'заявка будет автоматически закрыта.'
            f'{signature}'
        )

        form = NewEmailForm(initial=initial_data)

    context = {
        'incident': incident,
        'form': form,
        'first_email': first_email,
        'previous_plain': previous_plain,
        'previous_html': previous_html,
        'email_header': 'Уведомление заявителю о закрытии инцидента',
        'active_tab': 'email',
    }

    return render(request, template_name, context)
