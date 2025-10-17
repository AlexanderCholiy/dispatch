from datetime import datetime, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import Detail
from ts.models import AVRContractor, BaseStation, Pole

from .constants import (
    DEFAULT_AVR_CATEGORY,
    MAX_CODE_LEN,
    MAX_STATUS_COMMENT_LEN,
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

    class Meta:
        verbose_name = 'инцидент'
        verbose_name_plural = 'Инциденты'

    def __str__(self):
        return self.code or f'Внутренний номер {self.pk}'

    def save(self, *args, **kwargs):
        if self.is_incident_finish and not self.incident_finish_date:
            self.incident_finish_date = timezone.now()
        elif not self.is_incident_finish:
            # Если вдруг снова открыли:
            self.incident_finish_date = None

        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.categories.exists():
            avr_category, _ = IncidentCategory.objects.get_or_create(
                name=DEFAULT_AVR_CATEGORY
            )
            IncidentCategoryRelation.objects.get_or_create(
                incident=self,
                category=avr_category
            )

    @property
    def is_sla_expired(self) -> Optional[bool]:
        is_expired = None
        if self.incident_type and self.incident_type.sla_deadline:
            check_date = self.sla_check_date
            sla_deadline = self.incident_date + timedelta(
                minutes=self.incident_type.sla_deadline)
            is_expired = sla_deadline < check_date
        return is_expired
    is_sla_expired.fget.short_description = 'Просрочен ли SLA'

    @property
    def sla_check_date(self) -> datetime:
        if self.is_incident_finish and self.incident_finish_date:
            return self.incident_finish_date
        return timezone.now()

    @property
    def sla_deadline(self) -> Optional[datetime]:
        if self.incident_type and self.incident_type.sla_deadline:
            return self.incident_date + timedelta(
                minutes=self.incident_type.sla_deadline)
        return None
    sla_deadline.fget.short_description = 'Срок устранения'

    @property
    def avr_contractor(self) -> Optional[AVRContractor]:
        return self.pole.avr_contractor if self.pole else None
    avr_contractor.fget.short_description = 'Подрядчик по АВР'


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

    class Meta:
        verbose_name = 'история статусов инцидента'
        verbose_name_plural = 'История статусов инцидентов'
        unique_together = ('incident', 'status', 'insert_date')

    def __str__(self):
        return f'{self.status.name} [{self.insert_date}]'
