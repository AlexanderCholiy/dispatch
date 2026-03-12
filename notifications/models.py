from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .constants import (
    MAX_NOTIFICATION_LEVEL_LEN,
    MAX_NOTIFICATION_TEXT_LEN,
    MAX_NOTIFICATION_TITLE_LEN,
)


class NotificationLevel(models.TextChoices):
    LOW = ('low', 'Приоритет: Низкий')
    MEDIUM = ('medium', 'Приоритет: Средний')
    HIGH = ('high', 'Приоритет: Высокий')


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
        verbose_name='Пользователь',
    )
    title = models.CharField(
        max_length=MAX_NOTIFICATION_TITLE_LEN,
        verbose_name='Тема',
        db_index=True,
    )
    message = models.CharField(
        null=True,
        blank=True,
        max_length=MAX_NOTIFICATION_TEXT_LEN,
        verbose_name='Сообщение',
    )
    level = models.CharField(
        max_length=MAX_NOTIFICATION_LEVEL_LEN,
        choices=NotificationLevel.choices,
        default=NotificationLevel.MEDIUM,
        verbose_name='Приоритет',
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Дополнительные данные',
        help_text=(
            'Может содержать любые дополнительные сведения, например ссылки '
            'или ID объектов.'
        ),
    )
    read = models.BooleanField(
        default=False,
        verbose_name='Прочитано',
        db_index=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
    )
    send_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата отправки',
    )
    scheduled = models.BooleanField(
        default=False, verbose_name='Добавлено уведомление в Cellery'
    )

    class Meta:
        verbose_name = 'уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-send_at', '-created_at', '-id']
        indexes = [
            models.Index(fields=['user', 'read']),
            models.Index(fields=['send_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(send_at__gte=F('created_at')),
                name='send_after_created',
            ),
            models.UniqueConstraint(
                fields=['user', 'title', 'send_at'],
                name='unique_user_title_send_at'
            ),
        ]

    def __str__(self):
        return f'{self.user}: {self.title}'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.created_at = timezone.now()
        if self.send_at is None or self.send_at < self.created_at:
            self.send_at = self.created_at + timedelta(milliseconds=1)
        super().save(*args, **kwargs)

    def is_overdue(self):
        """Уведомление должно было быть отправлено, но еще не прочитано."""
        return not self.read and self.send_at <= timezone.now()
    is_overdue.boolean = True
    is_overdue.short_description = 'Просрочено'
