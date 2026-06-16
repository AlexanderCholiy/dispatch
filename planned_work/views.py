from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q, OuterRef, Subquery
from django.forms import formset_factory
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from core.constants import DATETIME_LOCAL_FORMAT
from core.services.get_raw_cookie import get_raw_cookie
from core.validators import get_aware_datetime
from incidents.services.get_avr_contractor_map import get_avr_contractor_map
from incidents.services.get_macroregions import get_macro_region_map
from incidents.services.get_region_responsible_manager import (
    get_region_responsible_managers,
)
from planned_work.annotations import annotate_plr_status
from planned_work.constants import (
    MAX_PLR_EMAILS_LINKS,
    MAX_PLR_PER_PAGE,
    PAGE_SIZE_PLR_CHOICES,
    PLR_CHANGE_LOG_PER_PAGE,
)
from planned_work.forms import (
    PlannedWorkEmailForm,
    PlannedWorkEmailFormSet,
    PlannedWorkForm
)
from planned_work.models import (
    PlannedWork,
    PlannedWorkChangeLog,
    PlannedWorkEmailLink,
    PlannedWorkReason,
    PlannedWorkStatus,
)
from ts.constants import UNDEFINED_CASE
from users.models import Roles, User
from users.utils import role_required
from incidents.models import Incident, IncidentStatusHistory

from .services.get_planned_work_author import get_planned_work_author


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='60/m', block=True)
def create_planned_work(request: HttpRequest):
    main_form = PlannedWorkForm(author_user=request.user)

    if request.method == 'POST' and 'planned_work_submit' in request.POST:
        main_form = PlannedWorkForm(request.POST, author_user=request.user)

        if main_form.is_valid():
            instance: PlannedWork = main_form.save(commit=False)
            instance.author = request.user
            instance.save()

            msg = f'Плановая работа "{instance}" успешно создана.'

            if instance.status == PlannedWorkStatus.PLANNED:
                messages.info(request, f'{msg}')
            elif instance.status == PlannedWorkStatus.COMPLETED:
                messages.success(request, f'{msg}')
            else:
                messages.success(request, f'{msg}')

            return redirect('planned_work:planned_work_detail', pk=instance.pk)

        messages.error(request, 'Исправьте ошибки в форме ПЛР')

    context = {
        'main_form': main_form,
        'can_manage': True,
        'active_tab': 'planned_work',
    }

    return render(request, 'planned_work/planned_work_detail.html', context)


@login_required
@role_required()
def planned_work_detail(request: HttpRequest, pk: int):
    planned_work = get_object_or_404(
        (
            PlannedWork.objects
            .select_related(
                'pole',
                'pole__region',
                'pole__region__macroregion',
                'pole__avr_contractor',
                'author',
            )
            .prefetch_related(
                'emails',
                Prefetch(
                    'change_logs',
                    queryset=PlannedWorkChangeLog.objects.select_related(
                        'changed_by'
                    ).order_by('-created_at', 'field_name')
                    [:PLR_CHANGE_LOG_PER_PAGE],
                    to_attr='prefetched_change_logs'
                ),
            )
        ),
        pk=pk
    )

    user: User = request.user
    if (
        user.role == Roles.AVR_CONTRACTOR
        and not planned_work.pole.avr_contractor == user.avr_contractor
    ):
        messages.error(
            request,
            (
                f'ПЛР {planned_work} не доступен вашей подрядной организации'
            )
        )
        return redirect(reverse(settings.LOGIN_URL))

    allowed_roles = [Roles.DISPATCH]
    can_manage = user.role in allowed_roles or user.is_superuser

    main_form = PlannedWorkForm(
        instance=planned_work, author_user=planned_work.author
    )

    related_emails_data = []
    for email_obj in planned_work.emails.all():
        related_emails_data.append({
            'id': email_obj.id,
            'email_date': email_obj.email_date,
        })
    initial_email_form_data = [
        {'email': email} for email in planned_work.emails.all()
    ]

    if not can_manage:
        for field_name in main_form.fields:
            main_form.fields[field_name].widget.attrs['disabled'] = True

    EmailFormSetClass = formset_factory(
        PlannedWorkEmailForm,
        extra=1 if can_manage else 0,
        can_delete=True if can_manage else False,
        max_num=MAX_PLR_EMAILS_LINKS,
        validate_max=True,
        formset=PlannedWorkEmailFormSet
    )

    email_formset = EmailFormSetClass(
        planned_work=planned_work,
        initial=initial_email_form_data,
        prefix='emails',
        author_user=user,
    )

    latest_status_subquery = IncidentStatusHistory.objects.filter(
        incident=OuterRef('pk')
    ).order_by('-insert_date', '-id')

    incidents = (
        Incident.objects
        .filter(pole=planned_work.pole, is_incident_finish=False)
        .select_related(
            'incident_type',
            'incident_subtype',
        )
        .prefetch_related('categories',)
        .annotate(
            latest_status_name=Subquery(
                latest_status_subquery.values('status__name')[:1]
            ),
            latest_status_date=Subquery(
                latest_status_subquery.values('insert_date')[:1]
            ),
            latest_status_class=Subquery(
                latest_status_subquery
                .values('status__status_type__css_class')[:1]
            ),
        )
        .order_by('incident_date', 'update_date', 'id')
    )
    incidents_total = len(incidents)

    if request.method == 'POST' and not can_manage:
        roles = [f'"{role.label}"' for role in allowed_roles]
        messages.error(
            request, f'Данная операция доступна только: {', '.join(roles)}'
        )
        return redirect('planned_work:planned_work_detail', pk=pk)

    if request.method == 'POST' and 'planned_work_submit' in request.POST:
        main_form = PlannedWorkForm(
            request.POST,
            author_user=planned_work.author,
            instance=planned_work,
        )

        if main_form.is_valid():
            instance: PlannedWork = main_form.save()

            msg = f'Плановая работа "{instance}" успешно обновлена.'

            if instance.status == PlannedWorkStatus.PLANNED:
                messages.info(request, f'{msg}')
            elif instance.status == PlannedWorkStatus.COMPLETED:
                messages.success(request, f'{msg}')
            else:
                messages.success(request, f'{msg}')

            return redirect('planned_work:planned_work_detail', pk=instance.pk)

        messages.error(request, 'Исправьте ошибки в форме ПЛР')

    if (
        request.method == 'POST'
        and 'planned_work_links_submit' in request.POST
    ):
        email_formset = EmailFormSetClass(
            request.POST,
            prefix='emails',
            planned_work=planned_work,
            author_user=user,
        )

        if email_formset.is_valid():
            email_formset.save()
            messages.success(request, 'Связи с письмами обновлены.')
            return redirect('planned_work:planned_work_detail', pk=pk)

        messages.error(request, 'Исправьте ошибки в форме связей с письмами')

    context = {
        'main_form': main_form,
        'email_formset': email_formset,
        'planned_work': planned_work,
        'incidents': incidents,
        'incidents_total': incidents_total,
        'related_emails_data': related_emails_data,
        'can_manage': can_manage,
    }

    return render(request, 'planned_work/planned_work_detail.html', context)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='200/m', block=True)
def planned_work_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()

    search_only_by_id = True if query and query.isdigit() else False

    sort = (
        request.GET.get('sort_planned_work')
        or (get_raw_cookie(request, 'sort_planned_work') or '').strip()
        or 'desc'
    )

    per_page = int(
        request.GET.get('per_page')
        or (get_raw_cookie(request, 'per_page_planned_work') or '').strip()
        or MAX_PLR_PER_PAGE
    )

    if per_page not in PAGE_SIZE_PLR_CHOICES:
        params = request.GET.copy()
        params['per_page'] = MAX_PLR_PER_PAGE
        return redirect(f'{request.path}?{params.urlencode()}')

    pole = (
        request.GET.get('planned_work_pole', '').strip()
        or (get_raw_cookie(request, 'planned_work_pole') or '').strip()
    ) if not search_only_by_id else None

    date_from = (
        request.GET.get('planned_work_date_from', '').strip()
        or (get_raw_cookie(request, 'planned_work_date_from') or '').strip()
        or None
    ) if not search_only_by_id else None
    date_from = get_aware_datetime(date_from, True)

    date_to = (
        request.GET.get('planned_work_date_to', '').strip()
        or (get_raw_cookie(request, 'planned_work_date_to') or '').strip()
        or None
    ) if not search_only_by_id else None
    date_to = get_aware_datetime(date_to, False)

    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    statuses = [st for st in PlannedWorkStatus]
    status = (
        request.GET.get('planned_work_status', '').strip()
        or (get_raw_cookie(request, 'planned_work_status') or '').strip()
    ).split(',') if not search_only_by_id else []

    status = (
        [v for v in status if v in statuses] or statuses[:]
    )

    reasons = [rs for rs in PlannedWorkReason]
    reason = (
        request.GET.get('reason', '').strip()
        or (get_raw_cookie(request, 'planned_work_reason') or '').strip()
    ).split(',') if not search_only_by_id else []

    reason = (
        [v for v in reason if v in reasons] or reasons[:]
    )

    responsible_users = get_planned_work_author()
    responsible_users_ids = [v['id'] for v in responsible_users]
    responsible_users_ids.append(0)  # отсутсвует
    responsible_user_id = (
        request.GET.get('planned_work_responsible_user', '')
        or (
            get_raw_cookie(request, 'planned_work_responsible_user') or ''
        ).strip()
    ).split(',') if not search_only_by_id else []

    responsible_user_id = [
        int(u) for u in responsible_user_id
        if u.isnumeric() and int(u) in responsible_users_ids
    ] or responsible_users_ids

    macroregions = get_macro_region_map()
    macroregion_ids = list(macroregions.keys())
    macroregion = (
        request.GET.get('planned_work_macroregion', '').strip()
        or (get_raw_cookie(request, 'planned_work_macroregion') or '').strip()
    ).split(',') if not search_only_by_id else []

    macroregion: list[int] = (
        [
            int(v) for v in macroregion
            if v.isnumeric() and int(v) in macroregion_ids
        ]
        or macroregion_ids[:]
    )

    avr_contractors = get_avr_contractor_map()
    avr_contractors = {0: 'Отсутствует', **avr_contractors}
    avr_contractors_ids = list(avr_contractors.keys())
    avr_contractor = (
        request.GET.get('planned_work_avr_contractor', '').strip()
        or (
            get_raw_cookie(request, 'planned_work_avr_contractor') or ''
        ).strip()
    ).split(',') if not search_only_by_id else []

    avr_contractor: list[int] = (
        [
            int(v) for v in avr_contractor
            if v.isnumeric() and int(v) in avr_contractors_ids
        ]
        or avr_contractors_ids[:]
    )

    region_responsible_managers = get_region_responsible_managers()
    region_responsible_managers = {
        'Отсутствует': [], **region_responsible_managers  # отсутсвует в начале
    }
    region_responsible_managers_keys = list(
        region_responsible_managers.keys()
    )
    region_responsible_manager = (
        request.GET.get('planned_work_region_responsible_manager', '').strip()
        or (
            get_raw_cookie(
                request, 'planned_work_region_responsible_manager'
            ) or ''
        ).strip()
    ).split(',') if not search_only_by_id else []

    region_responsible_manager = [
        v for v in region_responsible_manager
        if v in region_responsible_managers_keys
    ] or region_responsible_managers_keys

    base_qs = (
        PlannedWork.objects
        .select_related(
            'pole',
            'pole__region',
            'author',
        )
        .prefetch_related('emails',)
    )

    user: User = request.user
    if user.role == Roles.AVR_CONTRACTOR:
        base_qs = base_qs.filter(
            pole__avr_contractor=user.avr_contractor
        )

    if query:
        filters = (
            Q(emails__email_subject__icontains=query)
        )
        if query.isdigit():
            filters |= Q(pk=int(query))

        base_qs = base_qs.filter(filters).distinct()

    if pole:
        base_qs = base_qs.filter(pole__pole__startswith=pole)

    if date_from:
        base_qs = base_qs.filter(insert_date__gte=date_from)

    if date_to:
        base_qs = base_qs.filter(insert_date__lte=date_to)

    if macroregion and len(macroregion) != len(macroregion_ids):
        base_qs = base_qs.filter(
            pole__region__macroregion_id__in=macroregion
        )

    if (
        region_responsible_manager
        and len(region_responsible_manager) != len(
            region_responsible_managers_keys
        )
    ):
        if 'Отсутствует' in region_responsible_manager:
            regions_ids = []
            for mg in region_responsible_manager:
                if region_responsible_managers[mg]:
                    regions_ids.extend(region_responsible_managers[mg])
            base_qs = base_qs.filter(
                Q(pole__region_id__isnull=True)
                | Q(pole__region_id__in=regions_ids)
            )
        else:
            regions_ids = []
            for mg in region_responsible_manager:
                if region_responsible_managers[mg]:
                    regions_ids.extend(region_responsible_managers[mg])
            base_qs = base_qs.filter(pole__region_id__in=regions_ids)

    if avr_contractor and len(avr_contractor) != len(avr_contractors_ids):
        if 0 in avr_contractor:
            base_qs = base_qs.filter(
                Q(pole__isnull=True)
                | Q(pole__avr_contractor_id__isnull=True)
                | Q(pole__avr_contractor__contractor_name=UNDEFINED_CASE)
                | Q(pole__avr_contractor__in=avr_contractor)
            )
        else:
            base_qs = base_qs.filter(
                pole__avr_contractor_id__in=avr_contractor
            )

    if sort == 'asc':
        base_qs = base_qs.order_by('insert_date', 'id')
    else:
        base_qs = base_qs.order_by('-insert_date', 'id')

    base_qs = annotate_plr_status(base_qs)

    if status and len(status) != len(statuses):
        q_filter = Q()

        for status_val in status:
            if status_val == PlannedWorkStatus.PLANNED.value:
                q_filter |= Q(current_status=PlannedWorkStatus.PLANNED.value)
            elif status_val == PlannedWorkStatus.IN_PROGRESS.value:
                q_filter |= Q(
                    current_status=PlannedWorkStatus.IN_PROGRESS.value
                )
            elif status_val == PlannedWorkStatus.COMPLETED.value:
                q_filter |= Q(current_status=PlannedWorkStatus.COMPLETED.value)

        base_qs = base_qs.filter(q_filter)

    if reason and len(reason) != len(reasons):
        base_qs = base_qs.filter(reason__in=reason)

    if (
        responsible_user_id
        and len(responsible_user_id) != len(responsible_users_ids)
    ):
        not_responsioble_user = 0 in responsible_user_id

        if not_responsioble_user:
            base_qs = base_qs.filter(
                Q(author__isnull=True)
                | Q(author__id__in=responsible_user_id)
            )
        else:
            base_qs = base_qs.filter(
                author__id__in=responsible_user_id
            )

    paginator = Paginator(base_qs.values_list('id', flat=True), per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    page_ids = list(page_obj.object_list)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    user: User = request.user
    allowed_roles = [Roles.DISPATCH]
    can_manage = user.role in allowed_roles or user.is_superuser

    planned_work_qs = (
        PlannedWork.objects.filter(id__in=page_ids)
        .select_related(
            'pole',
            'pole__region',
            'author',
        )
        .prefetch_related(
            Prefetch(
                'email_links',
                queryset=(
                    PlannedWorkEmailLink.objects.select_related('email')
                    .order_by('-added_at', '-id')[:1]
                ),
                to_attr='latest_email_link'
            ),
        )
    )

    id_index = {id_: i for i, id_ in enumerate(page_ids)}
    planned_works = sorted(planned_work_qs, key=lambda n: id_index[n.id])

    context = {
        'page_obj': page_obj,
        'page_url_base': page_url_base,
        'planned_works': planned_works,
        'search_query': query,
        'statuses': PlannedWorkStatus,
        'reasons': PlannedWorkReason,
        'responsible_users': responsible_users,
        'avr_contractors': avr_contractors,
        'region_responsible_managers': region_responsible_managers,
        'macroregions': macroregions,
        'selected': {
            'status': status,
            'reason': reason,
            'responsible_user': responsible_user_id,
            'region_responsible_manager': region_responsible_manager,
            'macroregion': macroregion,
            'avr_contractor': avr_contractor,
            'pole': pole,
            'sort': sort,
            'date_from': (
                date_from.strftime(DATETIME_LOCAL_FORMAT) if date_from else ''
            ),
            'date_to': (
                date_to.strftime(DATETIME_LOCAL_FORMAT) if date_to else ''
            ),
            'per_page': per_page,
        },
        'page_size_choices': PAGE_SIZE_PLR_CHOICES,
        'can_manage': can_manage,
    }

    return render(request, 'planned_work/planned_work_list.html', context)
