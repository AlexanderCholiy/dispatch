from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from dal import autocomplete
from typing import Optional
from datetime import datetime

from emails.models import EmailMessage, EmailReference

from .constants import (
    MAX_CODE_LEN,
    MAX_FUTURE_END_DELTA,
    AVR_CATEGORY,
    RVR_CATEGORY,
    DGU_CATEGORY,
)
from .models import Incident, IncidentStatus, IncidentStatusHistory, TypeSubTypeRelation
from .utils import EmailNode, IncidentManager
from ts.models import Pole, BaseStation
from django.utils import timezone
from users.models import User, Roles
from .services.status_transition import get_allowed_statuses


class MoveEmailsForm(forms.Form):
    target_incident_code = forms.CharField(
        max_length=MAX_CODE_LEN,
        strip=True,
        label='Код инцидента',
    )
    email_ids = forms.JSONField()

    def __init__(
        self,
        email_tree: list[EmailNode],
        current_incident: Incident,
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.email_tree = email_tree
        self.current_incident = current_incident

    def clean_email_ids(self):
        email_ids_groups: list[list[int]] = self.cleaned_data['email_ids']

        if not isinstance(email_ids_groups, list):
            raise ValidationError('email_ids должен быть списком.')

        for group in email_ids_groups:
            if not isinstance(group, list):
                raise ValidationError('Каждая группа должна быть списком.')
            if not all(isinstance(i, int) for i in group):
                raise ValidationError(
                    'Все ID писем должны быть целыми числами.'
                )

        branch_ids: list[set[int]] = [
            set(root['branch_ids']) for root in self.email_tree
        ]
        for group in email_ids_groups:
            if not any(set(group) <= b_set for b_set in branch_ids):
                raise ValidationError(
                    f'Цепочка {group} некорректна. '
                    f'Возможно, данные были изменены. Проверьте историю '
                    f'инцидента {self.current_incident}.'
                )

        return email_ids_groups

    def clean_target_incident_code(self):
        code = self.cleaned_data['target_incident_code']
        if not code:
            raise ValidationError('Укажите код целевого инцидента.')

        incident = Incident.objects.filter(code=code).first()
        if not incident:
            raise ValidationError(f'Инцидент с кодом "{code}" не найден.')

        if self.current_incident and incident.pk == self.current_incident.pk:
            raise ValidationError(
                'Нельзя указать текущий инцидент в качестве целевого.'
            )

        return incident


class ConfirmMoveEmailsForm(forms.Form):
    source_incident_id = forms.IntegerField(widget=forms.HiddenInput())
    target_incident_code = forms.CharField(
        max_length=MAX_CODE_LEN,
        strip=True,
        label='Целевой инцидент',
        widget=forms.HiddenInput(),
    )
    email_ids = forms.JSONField(widget=forms.HiddenInput())

    def clean_source_incident_id(self):
        source_id = self.cleaned_data['source_incident_id']
        incident = Incident.objects.filter(pk=source_id).first()
        if not incident:
            raise ValidationError('Исходный инцидент не найден.')
        return incident

    def clean_target_incident_code(self):
        code = self.cleaned_data['target_incident_code']
        incident = Incident.objects.filter(code=code).first()
        if not incident:
            raise ValidationError(f'Инцидент с кодом "{code}" не найден.')
        return incident

    def clean_email_ids(self):
        email_ids_groups = self.cleaned_data['email_ids']

        if not isinstance(email_ids_groups, list):
            raise ValidationError('email_ids должен быть списком.')

        for group in email_ids_groups:
            if not isinstance(group, list):
                raise ValidationError('Каждая группа должна быть списком.')
            if not all(isinstance(i, int) for i in group):
                raise ValidationError(
                    'Все ID писем должны быть целыми числами.'
                )

        source_incident = self.cleaned_data.get('source_incident_id')
        if not source_incident:
            raise ValidationError('Исходный инцидент не найден.')

        emails = (
            EmailMessage.objects.filter(email_incident=source_incident)
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
            .order_by('-email_date', 'is_first_email')
        )

        source_email_tree = IncidentManager().build_email_tree(emails)
        branch_ids = [set(root['branch_ids']) for root in source_email_tree]

        for group in email_ids_groups:
            if not any(set(group) <= b_set for b_set in branch_ids):
                raise ValidationError(
                    f'Цепочка писем {group} больше не связана с исходным '
                    'инцидентом. '
                    f'Возможно, данные были изменены. Проверьте историю '
                    f'инцидента {source_incident}.'
                )

        return email_ids_groups


class IncidentForm(forms.ModelForm):
    new_status = forms.ModelChoiceField(
        queryset=IncidentStatus.objects.none(),
        required=True,
        label='Статус'
    )

    class Meta:
        model = Incident
        fields = (
            'pole',
            'base_station',
            'responsible_user',
            'incident_type',
            'incident_subtype',
            'new_status',
            'categories',
            'avr_start_date',
            'avr_end_date',
            'rvr_start_date',
            'rvr_end_date',
            'dgu_start_date',
            'dgu_end_date',
        )
        labels = {
            'pole': 'Опора',
            'base_station': 'Базовая станция',
            'responsible_user': 'Диспетчер',
            'incident_type': 'Тип инцидента',
            'incident_subtype': 'Подтип инцидента',
            'statuses': 'Статус',
            'categories': 'Категории инцидента',
            'avr_start_date': 'Передача на АВР',
            'avr_end_date': 'Закрытие АВР',
            'rvr_start_date': 'Передача на РВР',
            'rvr_end_date': 'Закрытие РВР',
            'dgu_start_date': 'Передача на ДГУ',
            'dgu_end_date': 'Закрытие ДГУ',
        }
        help_texts = {
            'pole': 'Шифр опоры',
            'base_station': 'Номер базовой станции, связанной с опорой',
            'avr_start_date': (
                'Дата и время уведомления подрядчика об '
                'аварийно-восстановительных работах'
            ),
            'avr_end_date': (
                'Дата и время завершения аварийно-восстановительных работ'
            ),
            'rvr_start_date': (
                'Дата и время уведомления подрядчика о '
                'ремонтно-восстановительных работах'
            ),
            'rvr_end_date': (
                'Дата и время завершения ремонтно-восстановительных работ'
            ),
            'dgu_start_date': (
                'Дата и время начала подачи электроэнергии от ДГУ'
            ),
            'dgu_end_date': (
                'Дата и время завершения подачи электроэнергии от ДГУ'
            ),
        }
        widgets = {
            'pole': autocomplete.ModelSelect2(
                url='ts:pole_autocomplete',
                attrs={'data-placeholder': 'Не выбрано'}
            ),
            'base_station': autocomplete.ModelSelect2(
                url='ts:bs_autocomplete',
                forward=['pole'],
                attrs={'data-placeholder': 'Не выбрано'}
            ),
            'avr_start_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'avr_end_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'rvr_start_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'rvr_end_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'dgu_start_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'dgu_end_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
        }

    def __init__(self, can_edit: bool = False, *args, **kwargs):
        self.can_edit = can_edit
        super().__init__(*args, **kwargs)

        # if not can_edit:
        #     for field in self.fields.values():
        #         field.disabled = True

        now = timezone.localtime()
        weekday = now.weekday()
        current_time = now.time()

        qs = User.objects.filter(
            is_active=True,
            role=Roles.DISPATCH
        ).select_related('work_schedule')

        working_users = [
            u.pk for u in qs
            if u.work_schedule
            and getattr(
                u.work_schedule,
                [
                    'monday',
                    'tuesday',
                    'wednesday',
                    'thursday',
                    'friday',
                    'saturday',
                    'sunday'
                ][weekday]
            )
            and (
                (
                    u.work_schedule.start_time
                    <= current_time
                    <= u.work_schedule.end_time
                )
                or u.work_schedule.start_time == u.work_schedule.end_time
            )
        ]

        self.fields['responsible_user'].queryset = qs.filter(
            pk__in=working_users
        )

        min_date = min(
            self.instance.insert_date or now,
            self.instance.incident_date or now
        )
        max_date = now + MAX_FUTURE_END_DELTA

        for field_name in [
            'avr_start_date', 'avr_end_date',
            'rvr_start_date', 'rvr_end_date',
            'dgu_start_date', 'dgu_end_date'
        ]:
            field = self.fields.get(field_name)

            if field:
                field.widget.attrs['min'] = min_date.strftime('%Y-%m-%dT%H:%M')
                field.widget.attrs['max'] = max_date.strftime('%Y-%m-%dT%H:%M')

        if self.instance.pk:
            last_status = self.instance.prefetched_status_history[0]
            last_status = last_status.status if last_status else None
        else:
            last_status = None

        allowed_statuses = get_allowed_statuses(last_status)

        self.fields['new_status'].queryset = allowed_statuses
        self.fields['new_status'].initial = last_status
        self.fields['new_status'].empty_label = None

        self.fields['new_status'].label_from_instance = lambda obj: obj.name
        self.status_classes = {
            s.pk: s.status_type.css_class for s in allowed_statuses
        }

        self.fields['responsible_user'].empty_label = 'Не назначен'
        self.fields['incident_type'].empty_label = 'Не выбрано'
        self.fields['incident_subtype'].empty_label = 'Не выбрано'

    def clean(self):
        cleaned_data = super().clean()
        pole = cleaned_data.get('pole')
        bs = cleaned_data.get('base_station')

        if bs:
            if not pole and bs.pole:
                cleaned_data['pole'] = bs.pole
                pole = bs.pole

            if pole and bs.pole and pole != bs.pole:
                self.add_error(
                    'base_station',
                    'Выбранная БС не соответствует выбранной опоре'
                )
                self.add_error(
                    'pole',
                    'Выбранная опора не соответствует выбранной БС'
                )

        return cleaned_data

    def clean_statuses(self):
        status = self.cleaned_data.get('statuses')
        if not status:
            raise forms.ValidationError('Выберите статус')

        allowed_qs = self.fields['statuses'].queryset
        if status not in allowed_qs:
            raise forms.ValidationError(
                'Переход в выбранный статус недоступен'
            )
        return status

    def clean_responsible_user(self):
        """Валидация пользователя только если он сменился"""
        user = self.cleaned_data.get('responsible_user')
        if not user:
            return None

        if self.instance.pk and user == self.instance.responsible_user:
            return user

        if not user.is_active or user.role != Roles.DISPATCH:
            raise ValidationError('Выбранный пользователь недоступен')

        if not user.work_schedule:
            return user

        now = timezone.localtime()
        weekday = now.weekday()
        current_time = now.time()

        weekday_attr = [
            'monday', 'tuesday', 'wednesday', 'thursday',
            'friday', 'saturday', 'sunday'
        ][weekday]

        # Проверяем, что в этот день у пользователя включена смена
        if not getattr(user.work_schedule, weekday_attr, False):
            raise ValidationError(
                f'Пользователь "{user}" не работает сегодня'
            )

        start_time = user.work_schedule.start_time
        end_time = user.work_schedule.end_time

        # Если start_time == end_time — значит круглосуточно
        if start_time != end_time:
            if not (start_time <= current_time <= end_time):
                raise ValidationError(
                    f'Пользователь "{user}" не работает в текущее время'
                )

        return user

    def clean_categories(self):
        """Должна быть выбрана хотя бы одна категория"""
        categories = self.cleaned_data.get('categories')
        if not categories.exists():
            raise ValidationError('Выберите хотя бы одну категорию инцидента')
        return categories

    def save(self, commit=True):
        instance = super().save(commit=commit)
        new_status = self.cleaned_data.get('new_status')

        last_status = self.instance.prefetched_status_history[0]
        current_status = last_status.status if last_status else None

        if new_status and new_status != current_status:
            category_names = set(
                instance.categories.all().values_list('name', flat=True)
            )
            IncidentStatusHistory.objects.create(
                incident=instance,
                status=new_status,
                is_avr_category=AVR_CATEGORY in category_names,
                is_rvr_category=RVR_CATEGORY in category_names,
                is_dgu_category=DGU_CATEGORY in category_names,
            )
            instance.statuses.add(new_status)

        return instance
