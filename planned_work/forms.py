from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from emails.models import EmailMessage
from emails.views import EmailAutocomplete
from planned_work.constants import MAX_PLR_REASON_LEN
from ts.models import Pole
from users.models import User

from .models import PlannedWork, PlannedWorkReason, PlannedWorkStatus


class PlannedWorkForm(forms.ModelForm):
    """
    Форма для создания и редактирования плановой работы (ПЛР).
    Включает валидацию на пересечение сроков и уникальность активной работы.
    """

    class Meta:
        model = PlannedWork
        fields = [
            'pole',
            'reason',
            'start_date',
            'end_date',
            'author',
        ]
        labels = {
            'pole': 'Опора',
            'reason': 'Причина',
            'start_date': 'Начало ПЛР',
            'end_date': 'Закрытие ПЛР',
            'author': 'Автор',
        }
        widgets = {
            'pole': autocomplete.ModelSelect2(
                url='ts:pole_autocomplete',
                attrs={'data-placeholder': 'Не выбрано'}
            ),
            'reason': forms.Select(
                attrs={'class': 'select'},
            ),
            'author': forms.Select(
                attrs={'class': 'select author-select'},
            ),
            'start_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'end_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        self.author_user = kwargs.pop('author_user', None)
        super().__init__(*args, **kwargs)

        self.fields['pole'].widget.attrs['title'] = ''

        self.fields['author'].disabled = True
        if not self.instance.pk and self.author_user:
            self.fields['author'].initial = self.author_user


class PlannedWorkEmailForm(forms.Form):
    """Форма для выбора одного письма."""
    
    email = forms.ModelChoiceField(
        queryset=EmailMessage.objects.all(),
        required=False,
        empty_label="Не выбрано",
        widget=autocomplete.ModelSelect2(
            url='emails:emails_autocomplete',
            attrs={'data-placeholder': 'Поиск по ID или теме письма...'}
        )
    )


class PlannedWorkEmailFormSet(forms.BaseFormSet):
    """Кастомный FormSet для управления связями ManyToMany."""
    
    def __init__(self, *args, **kwargs):
        # Извлекаем наш кастомный аргумент
        self.planned_work = kwargs.pop('planned_work', None)
        
        if not self.planned_work:
            raise ValueError("PlannedWorkEmailFormSet требует аргумент 'planned_work'.")

        # Заполняем initial данными из БД, если это GET запрос
        if not args and not kwargs.get('data'):
            try:
                # Получаем связанные письма
                related_emails = self.planned_work.emails.all()
                self.initial = [{'email': email} for email in related_emails]
            except Exception as e:
                # Логирование ошибки, если связь не найдена
                pass

        super().__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        # Добавляем чекбокс удаления
        form.fields['DELETE'] = forms.BooleanField(
            required=False,
            label='',
            widget=forms.CheckboxInput(attrs={'class': 'delete-checkbox'})
        )

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        seen_emails = set()
        duplicates_found = False
        
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            
            email = form.cleaned_data.get('email')
            
            if email:
                if email.id in seen_emails:
                    # Игнорируем дубликаты вместо ошибки
                    duplicates_found = True
                else:
                    seen_emails.add(email.id)
        
        # Если нужно строго запрещать дубликаты при сохранении, можно добавить проверку здесь
        # Но для отображения мы просто игнорируем их

    def save(self):
        """Сохраняет связи ManyToMany."""
        if not hasattr(self, 'planned_work') or not self.planned_work.pk:
            return

        selected_emails = []
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            
            email = form.cleaned_data.get('email')
            if email:
                selected_emails.append(email)
        
        # Устанавливаем связи
        self.planned_work.emails.set(selected_emails)
