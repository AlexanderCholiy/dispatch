from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import formset_factory
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit

from emails.models import EmailMessage
from planned_work.constants import MAX_PLR_EMAILS_LINKS
from planned_work.forms import PlannedWorkEmailForm, PlannedWorkForm
from planned_work.models import PlannedWork, PlannedWorkStatus
from users.models import Roles, User
from users.utils import role_required


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='60/m', block=True)
def create_planned_work(request: HttpRequest):
    user: User = request.user
    allowed_roles = [Roles.DISPATCH]
    can_manage = (
        user.role in allowed_roles or user.is_superuser or user.is_staff
    )

    PlannedWorkEmailFormSetFactory = formset_factory(
        PlannedWorkEmailForm,
        extra=1 if can_manage else 0,
        can_delete=True if can_manage else False,
        max_num=MAX_PLR_EMAILS_LINKS,
        validate_max=True
    )

    # if request.method == 'POST':
    #     # Инициализация основной формы
    #     main_form = PlannedWorkForm(request.POST, author_user=request.user)
        
    #     # Инициализация FormSet для писем с префиксом 'emails'
    #     email_formset = PlannedWorkEmailFormSet(request.POST, prefix='emails')

    #     # Проверяем валидность ОБЕИХ форм
    #     if main_form.is_valid() and email_formset.is_valid():
    #         # Сохраняем основную работу
    #         instance: PlannedWork = main_form.save(commit=False)
    #         instance.author = request.user
    #         instance.save()
            
    #         # ВАЖНО: Для ManyToMany нужно сохранять отдельно после сохранения объекта
    #         # Но так как мы управляем связями вручную через FormSet, save_m2m() нам не нужен для emails
    #         # Мы сделаем это сами ниже.
            
    #         # Очищаем все текущие связи с письмами перед добавлением новых
    #         instance.emails.clear()

    #         # Проходим по каждой строке в FormSet
    #         for form in email_formset:
    #             # Если чекбокс удаления НЕ отмечен
    #             if not form.cleaned_data.get('DELETE'):
    #                 email_obj = form.cleaned_data.get('email')
    #                 if email_obj:
    #                     instance.emails.add(email_obj)

    #         msg = f'Плановая работа "{instance}" успешно создана'
    #         status_label = PlannedWorkStatus(instance.status).label
            
    #         if instance.status == PlannedWorkStatus.PLANNED:
    #             messages.info(request, f'{msg} Статус: {status_label}')
    #         elif instance.status == PlannedWorkStatus.COMPLETED:
    #             messages.warning(request, f'{msg} Статус: {status_label}')
    #         else:
    #             messages.success(request, f'{msg} Статус: {status_label}')

    #         return redirect('planned_work:planned_work_create') # Замените на ваш URL списка работ

    # GET запрос
    main_form = PlannedWorkForm(author_user=request.user)

    email_formset = PlannedWorkEmailFormSetFactory(prefix='emails')

    context = {
        'main_form': main_form,
        'email_formset': email_formset,
    }

    return render(request, 'planned_work/planned_work_detail.html', context)
