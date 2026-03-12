from datetime import timedelta
from typing import Optional

from django import forms
from django.utils import timezone

from .models import Notification


class NotificationForm(forms.ModelForm):

    class Meta:
        model = Notification
        fields = ['title', 'message', 'level', 'read', 'send_at']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Введите тему уведомления'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Введите сообщение'
            }),
            'level': forms.Select(attrs={'class': 'select'}),
            'read': forms.Select(
                choices=(
                    (False, 'Не прочитано'),
                    (True, 'Прочитано'),
                ),
                attrs={'class': 'select'}
            ),
            'send_at': forms.DateTimeInput(
                attrs={'class': 'form-input', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance: Optional[Notification] = getattr(self, 'instance', None)
        now = timezone.localtime(timezone.now())
        min_date = now + timedelta(minutes=1)

        if instance and instance.pk:
            if instance.created_at:
                min_date = timezone.localtime(instance.created_at)

        min_date_str = min_date.strftime('%Y-%m-%dT%H:%M')
        self.fields['send_at'].widget.attrs['min'] = min_date_str

        if not self.initial.get('send_at'):
            self.initial['send_at'] = min_date_str

    def clean_send_at(self):
        send_at = self.cleaned_data.get('send_at')
        instance: Optional[Notification] = getattr(self, 'instance', None)

        if not send_at:
            return send_at

        now = timezone.now()

        if instance is None or instance.pk is None:
            if send_at < now:
                raise forms.ValidationError(
                    'Дата отправки не может быть в прошлом.'
                )
            return send_at

        created_at = instance.created_at
        created_at = timezone.localtime(created_at).replace(
            second=0, microsecond=0
        )
        if created_at and send_at < created_at:
            raise forms.ValidationError(
                'Дата отправки не может быть раньше даты создания '
                'уведомления.'
            )

        original_send_at = instance.send_at

        if original_send_at:
            original_cmp = original_send_at.replace(second=0, microsecond=0)
            new_cmp = send_at.replace(second=0, microsecond=0)

            if new_cmp == original_cmp:
                return original_send_at

        if send_at < now:
            raise forms.ValidationError(
                'Дата отправки не может быть в прошлом.'
            )

        return send_at
