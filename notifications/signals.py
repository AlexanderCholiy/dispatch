from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .constants import OLD_NOTIFICATIONS_TTL
from .models import Notification, NotificationLevel
from .tasks import send_notification_task


@receiver(post_save, sender=Notification)
def notify_notification_change(sender, instance: Notification, **kwargs):
    now = timezone.now()

    def schedule():
        if (
            (instance.scheduled and instance.read)
            or instance.read
            or instance.level == NotificationLevel.LOW
            or instance.send_at < now - OLD_NOTIFICATIONS_TTL
        ):
            if not instance.scheduled:
                Notification.objects.filter(
                    pk=instance.pk
                ).update(scheduled=True)
            return

        delay = max(0, int((instance.send_at - now).total_seconds()))
        send_notification_task.apply_async(
            args=[instance.id],
            countdown=delay
        )

    transaction.on_commit(schedule)
