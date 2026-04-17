import re

from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse

from notifications.models import Notification, NotificationLevel

from .models import User


def get_base_url():
    """
    Выбирает лучший базовый URL из доверенных источников.
    Приоритет: доменные имена над IP-адресами.
    """
    trusted = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])

    if not trusted:
        host = (
            settings.ALLOWED_HOSTS[0]
            if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*'
            else 'localhost:8000'
        )
        protocol = 'https' if not settings.DEBUG else 'http'
        return f'{protocol}://{host}'

    def is_ip(url):
        return bool(re.search(r'://\d+', url))

    sorted_origins = sorted(trusted, key=is_ip)

    return sorted_origins[0].rstrip('/')


@receiver(pre_save, sender=User)
def notify_role_or_staff_change(sender, instance: User, **kwargs):
    if instance.pk is None:
        return

    try:
        old_user = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return

    changes = []

    if old_user.role != instance.role:
        new_role: str = instance.get_role_display()
        old_role: str = old_user.get_role_display()
        changes.append(f'Ваш статус изменён: «{old_role}» → «{new_role}».')

    if old_user.is_staff != instance.is_staff:
        if instance.is_staff:
            admin_path = reverse('admin:index')
            base_url = get_base_url()
            full_url = f'{base_url}{admin_path}'

            changes.append(
                f'Статус доступа к панели управления предоставлен.\n\n'
                f'Войти можно по ссылке: {full_url}'
            )
        else:
            changes.append('Доступ к панели управления отозван.')

    if changes:
        Notification.objects.create(
            user=instance,
            title='Изменение прав доступа',
            message='\n\n'.join(changes),
            level=NotificationLevel.HIGH,
        )
