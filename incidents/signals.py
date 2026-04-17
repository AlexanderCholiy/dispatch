from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from api.serializers.comment import CommentSerializer
from users.models import User

from .models import Comment


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
