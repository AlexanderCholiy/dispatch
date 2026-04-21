from datetime import datetime
from typing import Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from api.serializers.comment import CommentSerializer
from core.loggers import celery_logger
from incidents.constants import AUTO_CLOSE_CACHE_KEY_PREFIX, AUTO_CLOSE_TTL
from incidents.tasks import close_incident_auto
from users.models import User

from .models import Comment, Incident


@receiver(post_save, sender=Comment)
def comment_saved_signal(sender, instance: Comment, created: bool, **kwargs):
    channel_layer = get_channel_layer()
    room_group_name = f'comments_{instance.incident_id}'

    serializer = CommentSerializer(instance)
    data = serializer.data

    if hasattr(instance, 'author'):
        author: User = instance.author
        if author.get_avatar_url:
            data['avatar_url'] = author.get_avatar_url
        else:
            data['avatar_url'] = None
        data['username'] = author.username
    else:
        data['avatar_url'] = None
        data['username'] = None

    async_to_sync(channel_layer.group_send)(
        room_group_name,
        {
            'type': 'broadcast_update',
            'action': 'created' if created else 'updated',
            'payload': data
        }
    )


@receiver(pre_delete, sender=Comment)
def comment_deleted_signal(sender, instance: Comment, **kwargs):
    channel_layer = get_channel_layer()
    room_group_name = f'comments_{instance.incident_id}'

    async_to_sync(channel_layer.group_send)(
        room_group_name,
        {
            'type': 'broadcast_update',
            'action': 'deleted',
            'payload': {'id': instance.id}
        }
    )


@receiver(pre_save, sender=Incident)
def preload_old_auto_close_date(sender, instance: Incident, **kwargs):
    """
    Перед сохранением загружаем старую дату из БД и кладем в Redis.
    Это позволит в post_save точно определить, изменилось ли поле.
    """
    if (
        instance.pk
        and instance.auto_close_date
        and not instance.is_incident_finish
    ):
        cache_key = f'{AUTO_CLOSE_CACHE_KEY_PREFIX}{instance.pk}'
        try:
            old_obj = (
                Incident.objects.only('auto_close_date').get(pk=instance.pk)
            )
            old_date = old_obj.auto_close_date
            val = old_date.isoformat() if old_date else None
            cache.set(cache_key, val, timeout=AUTO_CLOSE_TTL.seconds)

        except Incident.DoesNotExist:
            cache.delete(cache_key)


@receiver(post_save, sender=Incident)
def handle_auto_close_signal(
    sender,
    instance: Incident,
    created: bool,
    **kwargs
):
    """
    Сигнал, который срабатывает после сохранения модели Incident.
    Запускает задачу Celery, если была установлена дата автозакрытия.
    """
    current_auto_close_date = instance.auto_close_date

    if not current_auto_close_date or instance.is_incident_finish:
        if instance.pk:
            cache.delete(f'{AUTO_CLOSE_CACHE_KEY_PREFIX}{instance.pk}')
        return

    cache_key = f'{AUTO_CLOSE_CACHE_KEY_PREFIX}{instance.pk}'
    old_date_str: Optional[str] = cache.get(cache_key)

    old_auto_close_date = None
    if old_date_str:
        try:
            old_auto_close_date = datetime.fromisoformat(
                old_date_str.replace('Z', '+00:00')
            )
        except ValueError:
            pass

    is_changed = False

    if created:
        is_changed = True
    elif old_auto_close_date != current_auto_close_date:
        is_changed = True

    if not is_changed:
        celery_logger.debug(
            f'Инцидент {instance}: дата автозакрытия не изменилась '
            f'({current_auto_close_date}). Пропуск задачи.'
        )
        return

    if current_auto_close_date > timezone.now():
        close_incident_auto.apply_async(
            args=[instance.pk],
            eta=current_auto_close_date
        )
        msg = (
            f'Новый инцидент {instance}.'
            if created else f'Инцидент {instance}:'
        )
        celery_logger.debug(
            f'{msg} задача запланирована на {current_auto_close_date}'
        )
    else:
        close_incident_auto.delay(instance.pk)
        celery_logger.warning(
            f'Инцидент {instance}: дата просрочена, запуск немедленно.'
        )
