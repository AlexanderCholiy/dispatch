from functools import wraps
from typing import Callable

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import PendingUser, Roles, User
from .tasks import send_activation_email_task, send_confirm_email_task


def role_required(
    allowed_roles: list[Roles] = [Roles.DISPATCH, Roles.USER]
):
    """
    Декоратор который предоставляет доступ админу или у кого есть определенная
    роль
    """
    def decorator(view_func: Callable):
        @wraps(view_func)
        def wrapped_view(request: HttpRequest, *args, **kwargs):
            user: User = request.user
            if user.role not in allowed_roles and not user.is_superuser:
                if user.role == Roles.GUEST:
                    messages.success(
                        request,
                        (
                            'Вы успешно прошли регистрацию, теперь дождитесь '
                            'пока вашу учетную запись подтвердит администратор'
                        )
                    )
                else:
                    roles = [f'"{role.label}"' for role in allowed_roles]
                    messages.error(
                        request,
                        (
                            'Данная страница доступна только: '
                            f'{', '.join(roles)}'
                        )
                    )
                return redirect(reverse(settings.LOGIN_URL))
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator


def staff_required(view_func: Callable):
    """Декоратор который предоставляет доступ админу или персоналу"""
    @wraps(view_func)
    def wrapped_view(request: HttpRequest, *args, **kwargs):
        user: User = request.user
        if not user.is_superuser and not user.is_staff:
            messages.error(
                request,
                'Данная страница доступна только персоналу'
            )
            return redirect(reverse(settings.LOGIN_URL))
        return view_func(request, *args, **kwargs)
    return wrapped_view


def send_activation_email(
    pending_user: PendingUser, request: HttpRequest
):
    """
    Создаёт ссылку для активации пользователя и ставит задачу Celery
    на отправку email.
    """
    token = default_token_generator.make_token(pending_user)
    uid = urlsafe_base64_encode(force_bytes(pending_user.pk))

    activation_path = reverse(
        'users:activate', kwargs={'uidb64': uid, 'token': token}
    )
    activation_link = request.build_absolute_uri(activation_path)
    domain = request.get_host()

    send_activation_email_task.delay(
        pending_user_id=pending_user.pk,
        domain=domain,
        activation_link=activation_link,
    )


def send_confirm_email(pending_user: PendingUser, request: HttpRequest):
    """
    Создаёт ссылку для подтверждения смены email пользователя и ставит задачу
    Celery на отправку email.
    """
    token = default_token_generator.make_token(pending_user)
    uid = urlsafe_base64_encode(force_bytes(pending_user.pk))

    confirm_email_path = reverse(
        'users:confirm_email_change', kwargs={'uidb64': uid, 'token': token}
    )
    confirm_email_link = request.build_absolute_uri(confirm_email_path)
    domain = request.get_host()

    send_confirm_email_task.delay(
        pending_user_id=pending_user.pk,
        domain=domain,
        confirm_email_link=confirm_email_link,
    )
