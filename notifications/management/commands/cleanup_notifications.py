from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from notifications.models import Notification
from notifications.constants import (
    OLD_NOTIFICATIONS_TTL,
    NOTIFICATION_BATCH,
    UNREAD_NOTIFICATION_TTL,
)
from core.loggers import default_logger


class Command(BaseCommand):
    help = 'Удаляет старые и неактуальные уведомления'

    def handle(self, *args, **options):
        now = timezone.now()

        total_deleted = 0
        total_candidates = 0

        read_cutoff = now - OLD_NOTIFICATIONS_TTL

        read_qs = Notification.objects.filter(
            read=True,
            created_at__lt=read_cutoff,
        )

        total_candidates += read_qs.count()
        total_deleted += self._delete_queryset(read_qs)

        for level, ttl in UNREAD_NOTIFICATION_TTL.items():
            cutoff = now - ttl

            qs = Notification.objects.filter(
                read=False,
                level=level,
                created_at__lt=cutoff,
            )

            total_candidates += qs.count()
            total_deleted += self._delete_queryset(qs)

        if total_deleted:
            default_logger.info(
                f'Удалено {total_deleted} / {total_candidates} '
                f'не актуальных уведомлений'
            )

    def _delete_queryset(self, qs):
        deleted_total = 0

        while True:
            ids = list(
                qs.order_by('id')
                .values_list('id', flat=True)[:NOTIFICATION_BATCH]
            )

            if not ids:
                break

            with transaction.atomic():
                deleted, _ = Notification.objects.filter(
                    id__in=ids
                ).delete()

            deleted_total += deleted

        return deleted_total
