from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.loggers import default_logger
from notifications.constants import (
    NOTIFICATION_BATCH,
    OLD_NOTIFICATIONS_TTL,
    UNREAD_NOTIFICATION_TTL,
)
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Удаляет старые и неактуальные уведомления'

    def handle(self, *args, **options):
        now = timezone.now()

        total_deleted = 0
        total_candidates = 0

        read_cutoff = now - OLD_NOTIFICATIONS_TTL

        read_qs = Notification.objects.filter(
            read=True
        ).filter(
            Q(send_at__lt=read_cutoff)
            | Q(send_at__isnull=True, created_at__lt=read_cutoff)
        )

        total_candidates += read_qs.count()
        total_deleted += self._delete_queryset(read_qs)

        for level, ttl in UNREAD_NOTIFICATION_TTL.items():
            cutoff = now - ttl

            qs = Notification.objects.filter(
                read=False,
                level=level
            ).filter(
                Q(send_at__lt=cutoff)
                | Q(send_at__isnull=True, created_at__lt=cutoff)
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
