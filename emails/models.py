from datetime import datetime, timedelta
from typing import Optional

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from core.models import SpecialEmail, Attachment, Msg2, Detail
from core.constants import MAX_EMAIL_ID_LEN
from .constants import MAX_EMAIL_SUBJECT_LEN
from ts.models import Pole, BaseStation


User = get_user_model()


class EmailErr(SpecialEmail):
    """Письма обработанные с ошибкой"""

    class Meta:
        verbose_name = 'ошибка при обработки письма'
        verbose_name_plural = 'Ошибки обработки писем'

    def __str__(self):
        return self.email_msg_id


class EmailMessage(models.Model):
    """Основная модель для хранения писем"""
    email_msg_id = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        unique=True,
        null=False,
        verbose_name='ID сообщения',
    )
    email_msg_reply_id = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        null=True,
        blank=True,
        verbose_name='ID ответа на сообщение',
        db_index=True
    )
    email_subject = models.CharField(
        max_length=MAX_EMAIL_SUBJECT_LEN,
        null=True,
        blank=True,
        verbose_name='Тема письма',
        db_index=True
    )
    email_from = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        null=False,
        verbose_name='Адрес отправителя',
        db_index=True
    )
    email_date = models.DateTimeField(
        null=False,
        verbose_name='Дата и время получения письма',
        db_index=True
    )
    email_body = models.TextField(
        null=True,
        blank=True,
        verbose_name='Тело письма'
    )
    is_first_email = models.BooleanField(
        verbose_name='Является ли первым письмом в переписке',
        db_index=True
    )
    is_email_from_yandex_tracker = models.BooleanField(
        'Было ли письмо отправлено из YandexTracker',
        null=True,
        blank=True
    )
    was_added_2_yandex_tracker = models.BooleanField(
        'Было ли письмо добавлено в YandexTracker',
        null=True,
        blank=True
    )
    email_incident = models.ForeignKey(
        'Incident',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_messages',
        verbose_name='Номер инцидента',
        db_index=True
    )

    class Meta:
        verbose_name = 'сообщение'
        verbose_name_plural = 'Почта'

    def __str__(self):
        return self.email_msg_id


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


class EmailReference(models.Model):
    """Хранения ссылок на сообщения"""
    email_msg_references = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        null=False,
        verbose_name='Ссылка на другие сообщения'
    )
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='email_references',
        verbose_name='Сообщение',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'email_msg_references'],
                name='unique_email_reference'
            )
        ]
        verbose_name = 'ссылка на email'
        verbose_name_plural = 'Ссылки на email'

    def __str__(self):
        return self.email_msg_references


class EmailAttachment(Attachment):
    """Вложения прикрепленные к сообщению"""
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='email_attachments',
        verbose_name='Сообщение',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'file_name'],
                name='unique_email_attachment'
            )
        ]
        verbose_name = 'вложение email'
        verbose_name_plural = 'Вложения email'


class EmailInTextAttachment(Attachment):
    """Изображений вставленные в текст сообщения"""
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='email_intext_attachments',
        verbose_name='Сообщение',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'file_name'],
                name='unique_email_intext_attachment'
            )
        ]
        verbose_name = 'вложение в тексте email'
        verbose_name_plural = 'Вложения в тексте email'


class EmailTo(Msg2):
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        verbose_name='Сообщение',
        related_name='email_msg_to',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'email_to'],
                name='unique_email_to'
            )
        ]
        verbose_name = 'Получатель email'
        verbose_name_plural = 'Получатели email'


class EmailToCC(Msg2):
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        verbose_name='Сообщение',
        related_name='email_msg_cc',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'email_to'],
                name='unique_email_to_cc'
            )
        ]
        verbose_name = 'Получатель (в копии) email'
        verbose_name_plural = 'Получатели (в копии) email'


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
