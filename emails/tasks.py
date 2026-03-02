from typing import Optional

from celery import Task, shared_task
from celery.exceptions import SoftTimeLimitExceeded

from core.loggers import celery_logger
from incidents.constants import (
    AVR_CATEGORY,
    DGU_CATEGORY,
    ERR_STATUS_NAME,
    RVR_CATEGORY,
)
from incidents.models import IncidentStatus, IncidentStatusHistory

from .email_parser import email_parser
from .models import EmailMessage, EmailStatus
from .services.send_email_msg import send_via_django_email


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    queue='high',
    soft_time_limit=30,
    time_limit=40,
    acks_late=True,
)
def send_incident_email_task(
    self: Task,
    email_id: int,
    new_status_name: Optional[str] = None,
):
    try:
        email_msg = (
            EmailMessage.objects
            .select_related('folder', 'email_incident')
            .prefetch_related(
                'email_msg_to',
                'email_msg_cc',
                'email_references',
                'email_attachments',
                'email_intext_attachments',
            )
            .get(pk=email_id)
        )
    except EmailMessage.DoesNotExist:
        celery_logger.warning(f'Письмо id={email_id} не найдено')
        return

    if email_msg.status == EmailStatus.SENT:
        return

    email_msg.status = EmailStatus.SENDING
    email_msg.save(update_fields=['status'])

    try:
        send_via_django_email(
            email_msg=email_msg,
            smtp_user=email_parser.email_login,
            smtp_password=email_parser.email_pswd,
            smtp_host=email_parser.email_server,
        )

        email_msg.status = EmailStatus.SENT
        email_msg.save(update_fields=['status'])

        if new_status_name:
            incident = email_msg.email_incident
            if incident:
                new_status, _ = (
                    IncidentStatus.objects.get_or_create(name=new_status_name)
                )
                category_names = {c.name for c in incident.categories.all()}
                comments = (
                    'Статус добавлен автоматически после отправки автоответа.'
                )

                IncidentStatusHistory.objects.create(
                    incident=incident,
                    status=new_status,
                    comments=comments,
                    is_avr_category=AVR_CATEGORY in category_names,
                    is_rvr_category=RVR_CATEGORY in category_names,
                    is_dgu_category=DGU_CATEGORY in category_names,
                )
                incident.statuses.add(new_status)

    except SoftTimeLimitExceeded as exc:
        email_msg.status = EmailStatus.RETRY
        email_msg.save(update_fields=['status'])
        raise self.retry(exc=exc)

    except Exception as exc:
        email_msg.status = EmailStatus.RETRY
        email_msg.save(update_fields=['status'])

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        else:
            email_msg.status = EmailStatus.FAILED
            email_msg.save(update_fields=['status'])
            celery_logger.exception(
                f'[EMAIL] Все попытки исчерпаны id={email_msg.id}, '
                f'msg_id={email_msg.email_msg_id}. Ошибка: {exc}'
            )

            if new_status_name:
                incident = email_msg.email_incident
                if incident:
                    new_status, _ = (
                        IncidentStatus.objects
                        .get_or_create(name=ERR_STATUS_NAME)
                    )
                    category_names = {
                        c.name for c in incident.categories.all()
                    }
                    comments = (
                        'Статус добавлен автоматически после неудачной '
                        'отправки автоответа.'
                    )

                    IncidentStatusHistory.objects.create(
                        incident=incident,
                        status=new_status,
                        comments=comments,
                        is_avr_category=AVR_CATEGORY in category_names,
                        is_rvr_category=RVR_CATEGORY in category_names,
                        is_dgu_category=DGU_CATEGORY in category_names,
                    )
                    incident.statuses.add(new_status)
