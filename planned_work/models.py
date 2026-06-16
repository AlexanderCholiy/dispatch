from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.constants import MAX_LG_DESCRIPTION, MAX_ST_DESCRIPTION
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
    IN_PROGRESS = 'in-progress', 'В работе'
    COMPLETED = 'closed', 'Завершена'


class PlannedWorkEmailLink(models.Model):
    """Промежуточная модель для хранения времени добавления письма в связь"""

    planned_work = models.ForeignKey(
        'PlannedWork',
        on_delete=models.CASCADE,
        related_name='email_links'
    )
    email = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE
    )
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления в связь',
        db_index=True,
    )

    class Meta:
        unique_together = ('planned_work', 'email')
        ordering = ['-added_at', '-id']


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
        through=PlannedWorkEmailLink,
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

    @property
    def reason_label(self):
        """Возвращает человекочитаемое название причины."""
        try:
            return PlannedWorkReason(self.reason).label
        except ValueError:
            return self.reason

    def __str__(self):
        return f'ID: {self.pk}' if self.pk else 'Новый ПЛР'

    def clean(self):
        errors = {}

        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                errors['end_date'] = (
                    'Дата окончания не может быть раньше даты начала.'
                )

        if not self.pole_id:
            errors['pole'] = 'Опора обязательна для выбора.'
            raise ValidationError(errors)

        if errors:
            raise ValidationError(errors)

        # Ищем работы для этой же опоры и причины, исключая текущую:
        qs = PlannedWork.objects.filter(
            pole_id=self.pole_id,
            reason=self.reason
        )

        if self.pk:
            qs = qs.exclude(pk=self.pk)

        # 1. Проверяем пересечение с работами, у которых НЕТ даты окончания
        open_works = qs.filter(end_date__isnull=True)
        if self.end_date:
            open_works = open_works.filter(start_date__lt=self.end_date)

        # 2. Проверяем пересечение с работами, у которых ЕСТЬ дата окончания
        closed_works = qs.filter(end_date__isnull=False)
        if self.end_date:
            closed_works = closed_works.filter(
                start_date__lt=self.end_date,
                end_date__gt=self.start_date
            )
        else:
            closed_works = closed_works.filter(end_date__gt=self.start_date)

        conflicting_works = open_works | closed_works

        if conflicting_works.exists():
            conflicting = conflicting_works.first()
            errors['pole'] = (
                f'На данный период времени для этой опоры и причины уже '
                f'существует активная или запланированная работа '
                f'(ID: {conflicting.id})'
            )

        if errors:
            raise ValidationError(errors)


class PlannedWorkChangeLog(models.Model):
    """Детальный журнал изменений полей инцидента."""
    planned_work = models.ForeignKey(
        PlannedWork,
        on_delete=models.CASCADE,
        related_name='change_logs',
        verbose_name='Плановая работа',
        db_index=True
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Изменил пользователь',
        db_index=True
    )
    field_name = models.CharField(
        max_length=MAX_ST_DESCRIPTION,
        verbose_name='Поле',
        help_text='Название поля модели'
    )
    old_value = models.CharField(
        max_length=MAX_LG_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Старое значение',
        help_text='JSON строка или текст старого значения'
    )
    new_value = models.CharField(
        max_length=MAX_LG_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Новое значение',
        help_text='JSON строка или текст нового значения'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата изменения',
        db_index=True
    )

    class Meta:
        verbose_name = 'журнал'
        verbose_name_plural = 'Журналы изменений'
        ordering = ['-created_at', 'field_name', 'id']
        indexes = [
            models.Index(fields=['planned_work', '-created_at']),
        ]
        unique_together = ('planned_work', 'field_name', 'created_at')

    def clean(self):
        """Запрещает записи, если старое и новое значение идентичны."""
        super().clean()

        if not self.pk and self.old_value == self.new_value:
            raise ValidationError({
                'old_value': (
                    'Невозможно записать лог, '
                    'так как старое и новое значение идентичны.'
                ),
                'new_value': ('Значение не изменилось.')
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'{self.planned_work} | {self.field_name}: '
            f'{self.old_value} → {self.new_value}'
        )
