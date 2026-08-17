from django import forms

from .constants import MAX_COMMENT_LEN


class MaxConfirmNotificationForm(forms.Form):
    text = forms.CharField(
        label='Комментарий к уведомлению',
        required=False,
        max_length=MAX_COMMENT_LEN,
        widget=forms.Textarea(
            attrs={
                'placeholder': 'Введите комментарий к посту (необязательно)'
            }
        )
    )

    def clean_text(self):
        text: str = self.cleaned_data.get('text', '').strip()
        return text if text else None
