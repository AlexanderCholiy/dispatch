from django.db.models.signals import pre_save
from django.dispatch import receiver

from emails.services.turn_off_incident_auto_close import (
    turn_off_incident_auto_close,
)

from .models import EmailMessage


@receiver(pre_save, sender=EmailMessage)
def cancel_auto_close_on_new_email(
    sender, instance: EmailMessage, update_fields, **kwargs
):
    """
    Сбрасывает автозакрытие инцидента при появлении нового письма.
    Выполняется при создании нового письма.
    """
    if instance.pk:
        return

    turn_off_incident_auto_close(instance)
