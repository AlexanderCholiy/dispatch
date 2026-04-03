from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Comment
from api.serializers.comment import CommentSerializer


@receiver(post_save, sender=Comment)
def comment_saved_signal(sender, instance, created, update_fields, **kwargs):
    channel_layer = get_channel_layer()
    room_group_name = f'comments_{instance.incident_id}'

    serializer = CommentSerializer(instance)
    data = serializer.data

    event_type = 'comment_updated' if not created else 'comment_created'

    async_to_sync(channel_layer.group_send)(
        room_group_name,
        {
            'type': 'comment_event',
            'event_type': event_type,
            'data': data
        }
    )


@receiver(pre_delete, sender=Comment)
def comment_deleted_signal(sender, instance, **kwargs):
    channel_layer = get_channel_layer()
    room_group_name = f'comments_{instance.incident_id}'

    async_to_sync(channel_layer.group_send)(
        room_group_name,
        {
            'type': 'comment_event',
            'event_type': 'comment_deleted',
            'data': {'id': instance.id}
        }
    )
