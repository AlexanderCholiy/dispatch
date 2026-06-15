from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.forms import formset_factory
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django_ratelimit.decorators import ratelimit

from planned_work.constants import (
    MAX_PLR_EMAILS_LINKS,
    PLR_CHANGE_LOG_PER_PAGE,
    MAX_PLR_PER_PAGE,
    PAGE_SIZE_PLR_CHOICES,
)
from planned_work.forms import (
    PlannedWorkEmailForm,
    PlannedWorkEmailFormSet,
    PlannedWorkForm
)
from planned_work.models import (
    PlannedWork,
    PlannedWorkChangeLog,
    PlannedWorkStatus,
    PlannedWorkEmailLink,
)
from users.models import Roles, User
from users.utils import role_required
from core.services.get_raw_cookie import get_raw_cookie
from django.core.paginator import Paginator
from emails.models import EmailMessage


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
        'related_emails_data': related_emails_data,
        'can_manage': can_manage,
    }

    return render(request, 'planned_work/planned_work_detail.html', context)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='200/m', block=True)
def planned_work_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()

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

    base_qs = (
        PlannedWork.objects
        .select_related(
            'pole',
            'pole__region',
            'author',
        )
        .prefetch_related('emails',)
    )

    if sort == 'asc':
        base_qs = base_qs.order_by('insert_date', 'id')
    else:
        base_qs = base_qs.order_by('-insert_date', 'id')

    paginator = Paginator(base_qs.values_list('id', flat=True), per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    page_ids = list(page_obj.object_list)

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
        'planned_works': planned_works,
        'search_query': query,
        'selected': {
            'per_page': per_page,
            'sort': sort,
        },
        'page_size_choices': PAGE_SIZE_PLR_CHOICES,
        'can_manage': can_manage,
    }

    return render(request, 'planned_work/planned_work_list.html', context)
