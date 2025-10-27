from datetime import datetime, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.db.models import Q, F, CheckConstraint

from core.models import Detail
from ts.models import AVRContractor, BaseStation, Pole

from .constants import (
    AVR_CATEGORY,
    MAX_CODE_LEN,
    MAX_STATUS_COMMENT_LEN,
    RVR_SLA_DEADLINE_IN_HOURS,
)

User = get_user_model()


class Incident(models.Model):
    """Таблица инцидентов"""
    insert_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время добавления',
        db_index=True
    )
    update_date = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата и время редактирования'
    )
    incident_date = models.DateTimeField(
        null=False,
        verbose_name='Дата и время регистрации инцидента',
        db_index=True
    )
    is_incident_finish = models.BooleanField(
        default=False,
        verbose_name='Обработка заявки завершена',
        db_index=True
    )
    incident_finish_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время завершения инцидента',
        db_index=True
    )
    pole = models.ForeignKey(
        Pole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name='Связанная опора',
        db_index=True
    )
    base_station = models.ForeignKey(
        BaseStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name='Базовая станция',
        db_index=True
    )
    responsible_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name='Ответственный пользователь',
        db_index=True
    )
    incident_type = models.ForeignKey(
        'IncidentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name='Тип инцидента',
    )
    statuses = models.ManyToManyField(
        'IncidentStatus',
        through='IncidentStatusHistory',
        blank=True,
        related_name='incidents',
        verbose_name='Статус инцидента',
    )
    is_auto_incident = models.BooleanField(
        default=True,
        verbose_name='Сформирован автоматически',
    )
    code = models.CharField(
        verbose_name='Код',
        max_length=MAX_CODE_LEN,
        null=True,
        blank=True,
        unique=True,
        help_text='Используется в заголовках писем'
    )
    categories = models.ManyToManyField(
        'IncidentCategory',
        through='IncidentCategoryRelation',
        blank=True,
        related_name='incidents',
        verbose_name='Категории инцидента',
    )
    avr_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время передачи на АВР',
    )
    avr_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время закрытия АВР',
    )
    rvr_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время передачи на РВР',
    )
    rvr_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время закрытия РВР',
    )

    class Meta:
        verbose_name = 'инцидент'
        verbose_name_plural = 'Инциденты'
        constraints = [
            CheckConstraint(
                check=(
                    Q(avr_end_date__gte=F('avr_start_date'))
                    | Q(avr_end_date__isnull=True)
                    | Q(avr_start_date__isnull=True)
                ),
                name='avr_end_after_start',
            ),
            CheckConstraint(
                check=(
                    Q(rvr_end_date__gte=F('rvr_start_date'))
                    | Q(rvr_end_date__isnull=True)
                    | Q(rvr_start_date__isnull=True)
                ),
                name='rvr_end_after_start',
            )
        ]

    def __str__(self):
        return self.code or f'Внутренний номер {self.pk}'

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.is_incident_finish and not self.incident_finish_date:
            self.incident_finish_date = timezone.now()
        elif not self.is_incident_finish:
            # Если вдруг снова открыли:
            self.incident_finish_date = None

        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.categories.exists():
            avr_category, _ = IncidentCategory.objects.get_or_create(
                name=AVR_CATEGORY
            )
            IncidentCategoryRelation.objects.get_or_create(
                incident=self,
                category=avr_category
            )

    def clean(self):
        errors = {}

        if self.avr_start_date and self.avr_end_date:
            if self.avr_end_date < self.avr_start_date:
                errors['avr_end_date'] = (
                    'Дата закрытия АВР не может быть раньше даты начала.'
                )

        if self.rvr_start_date and self.rvr_end_date:
            if self.rvr_end_date < self.rvr_start_date:
                errors['rvr_end_date'] = (
                    'Дата закрытия РВР не может быть раньше даты начала.'
                )

        if errors:
            raise ValidationError(errors)

    @property
    def is_sla_avr_expired(self) -> Optional[bool]:
        is_expired = None
        if (
            self.incident_type
            and self.incident_type.sla_deadline
            and self.avr_start_date
        ):
            check_date = self.avr_end_date or timezone.now()
            sla_deadline = self.avr_start_date + timedelta(
                minutes=self.incident_type.sla_deadline
            )
            is_expired = sla_deadline < check_date
        return is_expired
    is_sla_avr_expired.fget.short_description = 'Просрочен ли SLA (АВР)'

    @property
    def is_sla_rvr_expired(self) -> Optional[bool]:
        is_expired = None
        if self.rvr_start_date:
            check_date = self.rvr_end_date or timezone.now()
            sla_deadline = self.rvr_start_date + timedelta(
                hours=RVR_SLA_DEADLINE_IN_HOURS
            )
            is_expired = sla_deadline < check_date
        return is_expired
    is_sla_rvr_expired.fget.short_description = 'Просрочен ли SLA (РВР)'

    @property
    def avr_contractor(self) -> Optional[AVRContractor]:
        return self.pole.avr_contractor if self.pole else None
    avr_contractor.fget.short_description = 'Подрядчик по АВР'

    @property
    def sla_avr_deadline(self) -> Optional[datetime]:
        if (
            self.incident_type
            and self.incident_type.sla_deadline
            and self.avr_start_date
        ):
            return self.avr_start_date + timedelta(
                minutes=self.incident_type.sla_deadline
            )
        return None
    sla_avr_deadline.fget.short_description = 'Срок устранения АВР'

    @property
    def sla_rvr_deadline(self) -> Optional[datetime]:
        if self.rvr_start_date:
            return self.rvr_start_date + timedelta(
                hours=RVR_SLA_DEADLINE_IN_HOURS
            )
        return None
    sla_rvr_deadline.fget.short_description = 'Срок устранения РВР'


class IncidentCategory(Detail):
    """Категории инцидентов"""
    class Meta:
        verbose_name = 'категория инцидента'
        verbose_name_plural = 'Категории инцидентов'

    def __str__(self):
        return self.name


class IncidentCategoryRelation(models.Model):
    """Связь инцидента и категории"""
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='incident_category_links',
        verbose_name='Инцидент'
    )
    category = models.ForeignKey(
        IncidentCategory,
        on_delete=models.CASCADE,
        related_name='incident_category_links',
        verbose_name='Категория'
    )

    class Meta:
        verbose_name = 'связь инцидента и категории'
        verbose_name_plural = 'Связи инцидентов и категорий'
        constraints = [
            models.UniqueConstraint(
                fields=['incident', 'category'],
                name='unique_incident_category'
            )
        ]

    def __str__(self):
        return f'{self.incident} - {self.category}'


class IncidentType(Detail):
    """Типы инцидентов"""
    sla_deadline = models.IntegerField(
        'Срок устранения аварии (мин)',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'тип инцидента'
        verbose_name_plural = 'Типы инцидентов'

    def clean(self):
        super().clean()
        if self.sla_deadline is not None and self.sla_deadline <= 0:
            raise ValidationError('SLA должен быть больше 0')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class IncidentStatus(Detail):
    """Таблица статусов"""

    class Meta:
        verbose_name = 'статус инцидента'
        verbose_name_plural = 'Статусы инцидентов'


class IncidentStatusHistory(models.Model):
    """Таблица статусов инцидентов"""
    incident = models.ForeignKey(
        Incident, related_name='status_history', on_delete=models.CASCADE)
    status = models.ForeignKey(
        IncidentStatus, related_name='status_history',
        on_delete=models.CASCADE
    )
    insert_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время добавления',
        db_index=True
    )
    comments = models.CharField(
        verbose_name='Комментарий',
        null=True,
        blank=True,
        max_length=MAX_STATUS_COMMENT_LEN,
    )
    is_avr_category = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Категория АВР'
    )
    is_rvr_category = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Категория РВР'
    )
    is_dgu_category = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Категория ДГУ'
    )

    class Meta:
        verbose_name = 'история статусов инцидента'
        verbose_name_plural = 'История статусов инцидентов'
        unique_together = ('incident', 'status', 'insert_date')

    def __str__(self):
        return f'{self.status.name} [{self.insert_date}]'
