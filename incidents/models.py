from datetime import datetime, timedelta
from typing import Optional

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from ts.models import Pole, BaseStation
from core.models import Detail

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
    track_sla = models.BooleanField(
        default=True,
        verbose_name='Отслеживать SLA',
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
    is_email_incident = models.BooleanField(
        verbose_name='Инцидент был зарегестрирован из почты',
        db_index=True
    )

    class Meta:
        verbose_name = 'инцидент'
        verbose_name_plural = 'Инциденты'

    @property
    def is_sla_expired(self) -> Optional[bool]:
        is_expired = None
        if self.incident_type and self.incident_type.sla_deadline:
            sla_deadline = self.incident_date + timedelta(
                minutes=self.incident_type.sla_deadline)
            is_expired = True if sla_deadline < timezone.now() else False
        return is_expired

    @property
    def sla_deadline(self) -> Optional[datetime]:
        sla_deadline = None
        if self.incident_type and self.incident_type.sla_deadline:
            sla_deadline = self.incident_date + timedelta(
                minutes=self.incident_type.sla_deadline)
        return sla_deadline


class IncidentType(Detail):
    """Типы инцидентов"""
    sla_deadline = models.IntegerField(
        'Срок устранения аварии (мин)',
        null=True,
        blank=True
    )
    is_avr_incident = models.BooleanField(
        'Можно ли этот инцидент назначить подрядчику',
        null=False,
        blank=False,
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

    class Meta:
        verbose_name = 'история статусов инцидента'
        verbose_name_plural = 'История статусов инцидентов'
        unique_together = ('incident', 'status', 'insert_date')

    def __str__(self):
        return f'{self.status.name} [{self.insert_date}]'
