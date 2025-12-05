from celery import Task, shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from django.core.mail import send_mail

from core.loggers import celery_logger
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

    subject = f'Подтверждение почты на {domain}'
    message = (
        f'Здравствуйте, {user.username}!\n\n'
        f'Вы указали этот адрес при регистрации на {domain}.\n'
        f'Для подтверждения перейдите по ссылке:\n{activation_link}\n\n'
        f'Срок действия ссылки — {valid_period}.\n\n'
        f'Если вы не регистрировались — просто проигнорируйте это письмо.'
    )

    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception as e:
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            celery_logger.error(
                f'Все попытки отправки email исчерпаны для {user.pk}.'
            )
            user.delete()
            return


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

    subject = f'Подтверждение смены email на {domain}'
    message = (
        f'Здравствуйте, {user.original_username}!\n\n'
        f'Вы запросили изменение email адреса на {domain}.\n'
        f'Новый email: {user.email}\n\n'
        f'Для подтверждения изменения перейдите по ссылке: \n'
        f'{confirm_email_link}\n\n'
        f'Срок действия ссылки — {valid_period}.\n\n'
        f'Если вы не запрашивали смену email — проигнорируйте это письмо.'
    )

    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception as e:
        try:
            raise self.retry(exc=e)
        except MaxRetriesExceededError:
            celery_logger.error(
                f'Все попытки отправки email исчерпаны для {user.pk}.'
            )
            user.delete()
            return


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

    subject = f'Восстановление пароля на {domain}'
    message = (
        f'Здравствуйте, {user.username}!\n\n'
        'Чтобы восстановить пароль, '
        f'перейдите по ссылке:\n{reset_password_link}\n\n'
        f'Если это были не вы — просто проигнорируйте это письмо.'
    )

    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception as e:
        raise self.retry(exc=e)
