from django import forms
from django.core.exceptions import ValidationError

from .models import Incident
from .constants import MAX_CODE_LEN
from .utils import EmailNode


class MoveEmailsForm(forms.Form):
    target_incident_code = forms.CharField(
        max_length=MAX_CODE_LEN,
        strip=True,
        label='Код инцидента',
    )
    email_ids = forms.JSONField()

    def __init__(
        self,
        email_tree: EmailNode,
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

        branch_ids = [set(root['branch_ids']) for root in self.email_tree]
        for group in email_ids_groups:
            if not any(set(group) <= b_set for b_set in branch_ids):
                raise ValidationError(f'Цепочка {group} некорректна.')

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
