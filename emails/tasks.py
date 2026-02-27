from celery import Task, shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

from core.loggers import celery_logger

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
    acks_late=True,  # чтобы при перезапуске сервера задача перезапустилась
)
def send_incident_email_task(self: Task, email_id: int):
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
        celery_logger.warning(
            f'Письмо id={email_id} не найдено'
        )
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

    except SoftTimeLimitExceeded as exc:

        email_msg.status = EmailStatus.RETRY
        email_msg.save(update_fields=['status'])

        raise self.retry(exc=exc)

    except Exception as exc:

        try:
            email_msg.status = EmailStatus.RETRY
            email_msg.save(update_fields=['status'])

            raise self.retry(exc=exc)

        except MaxRetriesExceededError:

            email_msg.status = EmailStatus.FAILED
            email_msg.save(update_fields=['status'])

            celery_logger.error(
                f'[EMAIL] Все попытки исчерпаны '
                f'id={email_msg.id}, msg_id={email_msg.email_msg_id}. '
                f'Ошибка: {exc}'
            )
