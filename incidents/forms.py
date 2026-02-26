import os
from datetime import datetime
from typing import Optional

from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import F, Prefetch, Q
from django.utils import timezone

from emails.constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_PREFIXES,
    MAX_ATTACHMENT_SIZE,
    MAX_EMAIL_LEN,
    MAX_EMAIL_SUBJECT_LEN,
    MAX_TOTAL_ATTACHMENTS_SIZE,
)
from emails.models import EmailMessage, EmailReference
from users.models import Roles, User

from .constants import (
    AVR_CATEGORY,
    DEFAULT_STATUS_NAME,
    DGU_CATEGORY,
    FINISHED_STATUS_NAMES,
    MAX_CODE_LEN,
    MAX_FUTURE_END_DELTA,
    RVR_CATEGORY,
)
from .models import (
    Incident,
    IncidentCategory,
    IncidentStatus,
    IncidentStatusHistory,
)
from .services.status_transition import get_allowed_statuses
from .utils import EmailNode, IncidentManager


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]

        total_size = 0

        for f in result:
            if not f:
                continue

            if f.size > MAX_ATTACHMENT_SIZE:
                limit_mb = MAX_ATTACHMENT_SIZE / (1024 * 1024)
                current_mb = round(f.size / (1024 * 1024), 2)
                raise ValidationError(
                    f'Файл "{f.name}" слишком большой ({current_mb} МБ). '
                    f'Максимальный размер одного файла: {int(limit_mb)} МБ.'
                )

            total_size += f.size

            ext = os.path.splitext(f.name)[1].lower()

            if not ext:
                raise ValidationError(
                    f'Файл "{f.name}" не имеет расширения. '
                    'Загрузка файлов без расширения запрещена.'
                )

            if ext not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f'Формат {ext} для файла "{f.name}" не поддерживается.'
                )

            file_mime = f.content_type
            is_mime_valid = any(
                file_mime == allowed
                or (allowed.endswith('/') and file_mime.startswith(allowed))
                for allowed in ALLOWED_MIME_PREFIXES
            )

            if not is_mime_valid:
                raise ValidationError(
                    f'Тип файла "{f.name}" ({file_mime}) не разрешен.'
                )

        if total_size > MAX_TOTAL_ATTACHMENTS_SIZE:
            total_mb = round(total_size / (1024 * 1024), 1)
            limit_total_mb = MAX_TOTAL_ATTACHMENTS_SIZE / (1024 * 1024)
            raise ValidationError(
                f'Общий объем вложений ({total_mb} МБ) превышает лимит '
                f'{int(limit_total_mb)} МБ.'
            )

        return result


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
        required=False,
        label='Статус'
    )

    class Meta:
        model = Incident
        fields = (
            'new_status',
            'pole',
            'base_station',
            'categories',
            'responsible_user',
            'incident_type',
            'incident_subtype',
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
                attrs={'data-placeholder': 'Не выбрано'},
            ),
            'avr_start_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'avr_end_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'rvr_start_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'rvr_end_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'dgu_start_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'dgu_end_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(
        self,
        can_edit: bool = False,
        author: Optional[User] = None,
        *args,
        **kwargs
    ):
        self.can_edit = can_edit
        self.author = author
        super().__init__(*args, **kwargs)

        # Значение по умолчанию для категории и статуса:
        if not self.instance.pk and not self.data:
            avr_category, _ = (
                IncidentCategory.objects.get_or_create(name=AVR_CATEGORY)
            )
            self.fields['categories'].initial = [avr_category]

        for field_name in [
            'avr_start_date', 'avr_end_date',
            'rvr_start_date', 'rvr_end_date',
            'dgu_start_date', 'dgu_end_date',
        ]:
            field = self.fields[field_name]
            if field:
                value: Optional[datetime] = getattr(self.instance, field_name)
                if value:
                    local_value = timezone.localtime(value).replace(
                        tzinfo=None
                    )
                    field.initial = local_value.strftime('%Y-%m-%dT%H:%M')

        if (
            self.data.get('categories')
            and isinstance(self.data['categories'], str)
        ):
            self.data = self.data.copy()
            self.data.setlist('categories', self.data['categories'].split(','))

        if not can_edit:
            for field in self.fields.values():
                field.disabled = True

        self.fields['pole'].widget.attrs['title'] = ''
        self.fields['base_station'].widget.attrs['title'] = ''

        now = timezone.localtime()
        weekday = now.weekday()
        current_time = now.time()

        days = [
            'monday',
            'tuesday',
            'wednesday',
            'thursday',
            'friday',
            'saturday',
            'sunday',
        ]
        current_day_field = days[weekday]
        day_filter = {f'work_schedule__{current_day_field}': True}

        self.fields['responsible_user'].queryset = User.objects.filter(
            is_active=True,
            role=Roles.DISPATCH,
            work_schedule__isnull=False,
            **day_filter
        ).filter(
            Q(
                work_schedule__start_time__lte=current_time,
                work_schedule__end_time__gte=current_time,
            )
            | Q(work_schedule__start_time=F('work_schedule__end_time'))
        ).select_related('work_schedule')

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
            last_status = (
                self.instance.prefetched_status_history[0]
                if self.instance.prefetched_status_history else None
            )
            last_status = last_status.status if last_status else None
        else:
            last_status = None

        allowed_statuses = get_allowed_statuses(last_status)

        self.fields['new_status'].queryset = allowed_statuses
        self.fields['new_status'].initial = last_status
        self.fields['new_status'].empty_label = None

        self.fields['new_status'].label_from_instance = lambda obj: obj.name

        # Для нового объекта ставим статус по умолчанию:
        if not self.instance.pk:
            default_status, _ = (
                IncidentStatus.objects.get_or_create(name=DEFAULT_STATUS_NAME)
            )
            self.fields['new_status'].initial = default_status
        else:
            self.fields['new_status'].initial = last_status

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
                    'БС не соответствует выбранной опоре'
                )
                self.add_error(
                    'pole',
                    'Опора не соответствует выбранной БС'
                )

        return cleaned_data

    def clean_categories(self):
        cats = self.cleaned_data.get('categories')
        if not cats:
            raise forms.ValidationError(
                'Выберите хотя бы одну категорию инцидента'
            )

        return cats

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

    def save(self, commit=True):
        instance: Incident = super().save(commit=False)

        new_status: Optional[IncidentStatus] = self.cleaned_data.get(
            'new_status'
        )

        # Получаем категории из формы
        cat_objs = self.cleaned_data.get('categories', [])

        if commit:
            instance.save()
            if cat_objs:
                instance.categories.set(cat_objs)

        category_names = {c.name for c in cat_objs} if cat_objs else set()

        # Определяем текущий статус
        last_status: Optional[IncidentStatusHistory] = (
            instance.prefetched_status_history[0]
            if getattr(instance, 'prefetched_status_history', None)
            else None
        )
        current_status = last_status.status if last_status else None

        # Если статус меняется
        if (
            (
                new_status
                and (not current_status or new_status.pk != current_status.pk)
            )
            or not new_status and not current_status
        ):
            if not new_status:
                new_status, _ = (
                    IncidentStatus.objects
                    .get_or_create(name=DEFAULT_STATUS_NAME)
                )
            # Создаём историю с актуальными категориями из формы

            comments = (
                f'Автор {self.author.get_full_name()} '
                f'[ID: {self.author.id}]'
            ) if self.author else None

            IncidentStatusHistory.objects.create(
                incident=instance,
                status=new_status,
                comments=comments,
                is_avr_category=AVR_CATEGORY in category_names,
                is_rvr_category=RVR_CATEGORY in category_names,
                is_dgu_category=DGU_CATEGORY in category_names,
            )
            instance.statuses.add(new_status)

        # Обновляем флаг завершённости
        instance.is_incident_finish = (
            new_status.name in FINISHED_STATUS_NAMES if new_status else False
        )

        # Сохраняем instance и категории
        if commit:
            instance.save()
            if cat_objs:
                instance.categories.set(cat_objs)

        return instance


class NewEmailForm(forms.Form):
    to = forms.CharField(
        label='Кому',
        widget=forms.TextInput(
            attrs={'placeholder': 'ivanov@mail.ru, petrov@mail.ru...'}
        ),
    )
    cc = forms.CharField(
        label='Копия (CC)',
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'ivanov@mail.ru, petrov@mail.ru...'}
        ),
    )
    subject = forms.CharField(
        label='Тема письма',
        max_length=MAX_EMAIL_SUBJECT_LEN,
        widget=forms.TextInput(attrs={'placeholder': 'Введите тему письма'})
    )
    body = forms.CharField(
        label='Текст письма',
        required=False,
        widget=forms.Textarea(
            attrs={'placeholder': 'Введите текст письма'}
        )
    )
    attachments = MultipleFileField(
        label='Прикрепить файлы',
        required=False,
    )

    def _clean_email_list(self, data):
        if not data:
            return []

        emails = [e.strip() for e in data.split(',') if e.strip()]

        for email in emails:
            validate_email(email)

            if len(email) > MAX_EMAIL_LEN:
                raise ValidationError(
                    f'Email "{email[:30]}..." слишком длинный. '
                    f'Максимальная длина одного адреса — {MAX_EMAIL_LEN} '
                    'символа.'
                )

        return emails

    def clean_to(self):
        emails = self._clean_email_list(self.cleaned_data.get('to', ''))
        if not emails:
            raise ValidationError('Поле "Кому" не может быть пустым.')
        return emails

    def clean_cc(self):
        return self._clean_email_list(self.cleaned_data.get('cc', ''))
