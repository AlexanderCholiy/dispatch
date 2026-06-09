from django.shortcuts import render, redirect

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.utils import role_required
from django_ratelimit.decorators import ratelimit
from planned_work.forms import PlannedWorkForm, PlannedWorkEmailFormSet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from planned_work.models import PlannedWork, PlannedWorkStatus
from django.forms import modelformset_factory


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='60/m', block=True)
def create_planned_work(request: HttpRequest):
    if request.method == 'POST':
        # Инициализация основной формы
        main_form = PlannedWorkForm(request.POST, author_user=request.user)
        
        # Инициализация FormSet для писем с префиксом 'emails'
        email_formset = PlannedWorkEmailFormSet(request.POST, prefix='emails')

        # Проверяем валидность ОБЕИХ форм
        if main_form.is_valid() and email_formset.is_valid():
            # Сохраняем основную работу
            instance: PlannedWork = main_form.save(commit=False)
            instance.author = request.user
            instance.save()
            
            # ВАЖНО: Для ManyToMany нужно сохранять отдельно после сохранения объекта
            # Но так как мы управляем связями вручную через FormSet, save_m2m() нам не нужен для emails
            # Мы сделаем это сами ниже.
            
            # Очищаем все текущие связи с письмами перед добавлением новых
            instance.emails.clear()

            # Проходим по каждой строке в FormSet
            for form in email_formset:
                # Если чекбокс удаления НЕ отмечен
                if not form.cleaned_data.get('DELETE'):
                    email_obj = form.cleaned_data.get('email')
                    if email_obj:
                        instance.emails.add(email_obj)

            msg = f'Плановая работа "{instance}" успешно создана'
            status_label = PlannedWorkStatus(instance.status).label
            
            if instance.status == PlannedWorkStatus.PLANNED:
                messages.info(request, f'{msg} Статус: {status_label}')
            elif instance.status == PlannedWorkStatus.COMPLETED:
                messages.warning(request, f'{msg} Статус: {status_label}')
            else:
                messages.success(request, f'{msg} Статус: {status_label}')

            return redirect('planned_work:planned_work_create') # Замените на ваш URL списка работ

    else:
        # GET запрос
        main_form = PlannedWorkForm(author_user=request.user)
        
        # Для FormSet при создании передаем пустой список initial, 
        # но extra=1 создаст одну пустую строку автоматически
        email_formset = PlannedWorkEmailFormSet(prefix='emails')

    context = {
        'form': main_form,
        'email_formset': email_formset,
        'title': 'Создание новой плановой работы',
    }
    
    # Убедитесь, что рендерится правильный шаблон (у вас в коде был detail.html, но функция create)
    return render(request, 'planned_work/planned_work_detail.html', context)
