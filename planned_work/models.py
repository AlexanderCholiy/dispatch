from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from emails.models import EmailMessage
from planned_work.constants import MAX_PLR_REASON_LEN
from ts.models import Pole
from users.models import User


class PlannedWorkReason(models.TextChoices):
    """Причины проведения плановых работ"""
    POWER_OFF = ('power_off', 'Отключение питания')
    PREVENTIVE_MAINTENANCE = (
        'preventive_maintenance', 'Плановое обслуживание'
    )
    EQUIPMENT_UPGRADE = ('equipment_upgrade', 'Модернизация оборудования')
    CABLE_REPLACEMENT = ('cable_replacement', 'Замена кабельной линии')
    INSTALLATION = ('installation', 'Установка нового оборудования')
    INSPECTION = ('inspection', 'Инспекция / Обследование')
    OTHER = ('other', 'Иное')


class PlannedWorkStatus(models.TextChoices):
    """Статусы плановой работы"""
    PLANNED = 'planned', 'В планах'
    IN_PROGRESS = 'in_progress', 'В работе'
    COMPLETED = 'completed', 'Завершена'


class PlannedWork(models.Model):
    """Журнал плановых работ (ПЛР)"""
    pole = models.ForeignKey(
        Pole,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name='planned_works',
        verbose_name='Опора',
        db_index=True,
    )
    reason = models.CharField(
        max_length=MAX_PLR_REASON_LEN,
        choices=PlannedWorkReason.choices,
        verbose_name='Причина',
        db_index=True,
    )
    start_date = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата и время начала ПЛР',
        db_index=True,
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время окончания ПЛР',
        db_index=True,
    )
    emails = models.ManyToManyField(
        EmailMessage,
        related_name='planned_works',
        blank=True,
        verbose_name='Связанные письма',
        help_text='Письма, связанные с данной плановой работой'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planned_works',
        verbose_name='Автор',
        db_index=True,
    )
    insert_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время добавления',
        db_index=True,
    )

    class Meta:
        verbose_name = 'ПЛР'
        verbose_name_plural = 'Плановые работы'

        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(end_date__gte=models.F('start_date'))
                    | models.Q(end_date__isnull=True)
                ),
                name='planned_work_end_after_start',
            ),
            models.UniqueConstraint(
                fields=['pole', 'reason'],
                condition=models.Q(end_date__isnull=True),
                name='unique_open_planned_work_per_pole_reason',
            ),
            models.UniqueConstraint(
                fields=['pole', 'reason', 'end_date'],
                condition=models.Q(end_date__isnull=False),
                name='unique_planned_work_end_date',
            ),
            models.UniqueConstraint(
                fields=['pole', 'reason', 'start_date'],
                condition=models.Q(end_date__isnull=False),
                name='unique_planned_work_start_date',
            ),
        ]

    @property
    def status(self) -> str:
        """
        Динамический статус работы на основе текущего времени.
        Возвращает ключ из PlannedWorkStatus (например, 'in_progress').
        """
        now = timezone.now()

        if self.end_date and self.end_date <= now:
            return PlannedWorkStatus.COMPLETED

        if self.start_date <= now:
            return PlannedWorkStatus.IN_PROGRESS

        return PlannedWorkStatus.PLANNED

    def __str__(self):
        return (
            f'{PlannedWorkReason(self.reason).label} на {self.pole}'
        )

    def clean(self):
        errors = {}
        now = timezone.now()

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors['end_date'] = (
                    'Дата окончания не может быть раньше даты начала.'
                )

        if not self.pole_id:
            errors['pole'] = 'Опора обязательна для выбора.'
            raise ValidationError(errors)

        qs = PlannedWork.objects.filter(
            pole_id=self.pole_id,
            reason=self.reason
        ).exclude(pk=self.pk)

        # Фильтруем только те, которые активны сейчас:
        active_works = qs.filter(
            models.Q(end_date__isnull=True)
            | models.Q(end_date__gt=now)
        ).filter(
            start_date__lte=now
        )

        if active_works.exists():
            conflicting = active_works.first()
            errors['pole'] = (
                f'Для данной опоры и причины уже существует '
                f'активная плановая работа '
                f'(ID: {conflicting.id})'
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
