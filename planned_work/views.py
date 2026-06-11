from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import formset_factory, modelformset_factory
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from django.shortcuts import redirect, render, get_object_or_404
from django_ratelimit.decorators import ratelimit

from emails.models import EmailMessage
from planned_work.constants import MAX_PLR_EMAILS_LINKS
from planned_work.forms import PlannedWorkEmailForm, PlannedWorkForm, PlannedWorkEmailFormSet
from planned_work.models import PlannedWork, PlannedWorkStatus
from users.models import Roles, User
from users.utils import role_required


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

        messages.error(request, 'Исправьте ошибки в формах ПЛР')

    context = {
        'main_form': main_form,
        'can_manage': True,
        'active_tab': 'planned_work',
    }

    return render(request, 'planned_work/planned_work_detail.html', context)


@login_required
@role_required()
def planned_work_detail(request: HttpRequest, pk: int):
    planned_work = get_object_or_404(PlannedWork, pk=pk)

    user: User = request.user
    allowed_roles = [Roles.DISPATCH]
    can_manage = user.role in allowed_roles or user.is_superuser

    main_form = PlannedWorkForm(
        instance=planned_work, author_user=planned_work.author
    )

    if not can_manage:
        for field_name in main_form.fields:
            main_form.fields[field_name].widget.attrs['disabled'] = True

    EmailFormSetClass = formset_factory(
        PlannedWorkEmailForm,
        extra=1,
        can_delete=True,
        max_num=10,
        validate_max=True,
        formset=PlannedWorkEmailFormSet
    )

    email_formset = EmailFormSetClass(
        planned_work=planned_work,
        prefix='emails',
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

            msg = f'Плановая работа "{instance}" успешно создана.'

            if instance.status == PlannedWorkStatus.PLANNED:
                messages.info(request, f'{msg}')
            elif instance.status == PlannedWorkStatus.COMPLETED:
                messages.success(request, f'{msg}')
            else:
                messages.success(request, f'{msg}')

            return redirect('planned_work:planned_work_detail', pk=instance.pk)

        messages.error(request, 'Исправьте ошибки в формах ПЛР')

    context = {
        'main_form': main_form,
        'email_formset': email_formset,
        'planned_work': planned_work,
        'can_manage': can_manage,
    }

    return render(request, 'planned_work/planned_work_detail.html', context)
