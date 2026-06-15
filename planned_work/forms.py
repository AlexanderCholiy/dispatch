from dal import autocomplete
from django import forms

from core.loggers import django_logger
from emails.models import EmailMessage
from planned_work.services.log_planned_work_changes import (
    log_planned_work_changes,
)

from .models import PlannedWork


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

        self._old_instance = None

        if self.instance.pk:
            try:
                self._old_instance = (
                    PlannedWork.objects
                    .select_related('pole', 'author')
                    .prefetch_related('emails')
                    .get(pk=self.instance.pk)
                )
            except PlannedWork.DoesNotExist:
                pass

    def save(self, commit=True):
        instance = super().save(commit=False)

        if not instance.author_id and self.author_user:
            instance.author = self.author_user

        if commit:
            instance.save()

            if self._old_instance:
                log_planned_work_changes(
                    old_instance=self._old_instance,
                    new_instance=instance,
                    changed_by=self.author_user,
                )
            else:
                pass

        return instance


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
        self.planned_work = kwargs.pop('planned_work', None)
        self.author_user = kwargs.pop('author_user', None)

        if not self.planned_work:
            raise ValueError(
                'PlannedWorkEmailFormSet требует аргумент "planned_work".'
            )

        if not args and not kwargs.get('data'):
            try:
                related_emails = self.planned_work.emails.all()
                self.initial = [{'email': email} for email in related_emails]
            except Exception as e:
                django_logger.exception(
                    f'Связь PlannedWork/EmailMessage не найдена: {e}'
                )
                pass

        super().__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super().add_fields(form, index)
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

        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue

            email = form.cleaned_data.get('email')

            if email:
                if email.id not in seen_emails:
                    seen_emails.add(email.id)

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

        old_email_ids = list(
            self.planned_work.emails.values_list('id', flat=True)
        )

        self.planned_work.emails.set(selected_emails)

        log_planned_work_changes(
            old_instance=None,
            new_instance=self.planned_work,
            changed_by=self.author_user,
            old_email_ids=old_email_ids,
        )
