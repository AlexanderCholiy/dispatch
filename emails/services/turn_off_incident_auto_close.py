from core.loggers import incident_logger
from emails.models import EmailMessage
from incidents.models import Incident


def turn_off_incident_auto_close(email: EmailMessage):
    """
    Сбрасывает автозакрытие инцидента.
    """
    if not email.email_incident_id:
        return

    try:
        incident = Incident.objects.only(
            'auto_close_date', 'is_incident_finish'
        ).get(
            pk=email.email_incident_id
        )
    except Incident.DoesNotExist:
        return

    if incident.is_incident_finish:
        return

    if incident.auto_close_date is not None:
        incident.auto_close_date = None
        incident.save(update_fields=['auto_close_date'])

        incident_logger.debug(
            f'Создание письма {email}: '
            f'сброшено автозакрытие инцидента {incident}'
        )
