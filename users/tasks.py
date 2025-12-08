from celery import Task, shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings

from core.loggers import celery_logger
from core.services.email import EmailService
from core.utils import timedelta_to_human_time

from .models import PendingUser, User


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue='default',
)
def send_activation_email_task(
    self: Task, pending_user_id: int, domain: str, activation_link: str
):
    try:
        user = PendingUser.objects.get(pk=pending_user_id)
    except PendingUser.DoesNotExist:
        celery_logger.warning(
            f'Пользователь с id={pending_user_id} уже удалён'
        )
        return

    valid_period = timedelta_to_human_time(
        settings.REGISTRATION_ACCESS_TOKEN_LIFETIME
    )

    email = EmailService(
        template='services/activation_email.html',
        subject=f'Подтверждение регистрации на {domain}',
        domain=domain,
        context={
            'username': user.username,
            'domain': domain,
            'activation_link': activation_link,
            'valid_period': valid_period,
            'logo_cid': 'logo',
        },
    ).build_html_email(user)

    try:
        email.send()
    except Exception as e:
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            celery_logger.error(
                f'Все попытки отправки email исчерпаны для {user.pk}.'
            )
            user.delete()
            return
    else:
        user.delete()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue='default',
)
def send_confirm_email_task(
    self: Task, pending_user_id: int, domain: str, confirm_email_link: str
):
    try:
        user = PendingUser.objects.get(pk=pending_user_id)
    except PendingUser.DoesNotExist:
        celery_logger.warning(
            f'Пользователь с id={pending_user_id} уже удалён'
        )
        return

    valid_period = timedelta_to_human_time(
        settings.REGISTRATION_ACCESS_TOKEN_LIFETIME
    )

    email = EmailService(
        template='services/confirm_email.html',
        subject=f'Подтверждение смены email на {domain}',
        domain=domain,
        context={
            'username': user.original_username,
            'domain': domain,
            'confirm_email_link': confirm_email_link,
            'valid_period': valid_period,
            'logo_cid': 'logo',
        },
    ).build_html_email(user)

    try:
        email.send()
    except Exception as e:
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            celery_logger.error(
                f'Все попытки отправки email исчерпаны для {user.pk}.'
            )
            user.delete()
            return
    else:
        user.delete()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue='default',
)
def send_password_reset_email_task(
    self: Task, user_id: int, domain: str, reset_password_link: str
):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    valid_period = timedelta_to_human_time(
        settings.REGISTRATION_ACCESS_TOKEN_LIFETIME
    )

    email = EmailService(
        template='services/password_reset_email.html',
        subject=f'Сброс пароля на {domain}',
        domain=domain,
        context={
            'username': user.username,
            'domain': domain,
            'reset_password_link': reset_password_link,
            'valid_period': valid_period,
            'logo_cid': 'logo',
        },
    ).build_html_email(user)

    try:
        email.send()
    except Exception as e:
        raise self.retry(exc=e)
