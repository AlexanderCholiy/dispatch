from django.db import models
from django.utils import timezone

from .constants import MAX_FIELD_PREVIEW_LENGTH


class EnergyModel(models.Model):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='id',
    )

    class Meta:
        abstract = True


class EnergyAttr(EnergyModel):
    attr_type = models.ForeignKey(
        'AttrType',
        on_delete=models.DO_NOTHING,
        db_column='constant_type',
        to_field='attribute_id',
    )
    text = models.TextField(
        'Значение',
        null=True,
        blank=True,
        db_column='constant_text',
    )
    created_at = models.DateTimeField(
        'Добавлено в',
        default=timezone.now,
        db_column='time_stamp',
    )

    class Meta:
        abstract = True

    def __str__(self):
        value = self.text or ''
        value = value.strip()
        value = (
            f'{value[:MAX_FIELD_PREVIEW_LENGTH]}...'
        ) if len(value) > MAX_FIELD_PREVIEW_LENGTH else value
        return f'{self.attr_type}: {value}'


class EnergyRequest(EnergyModel):
    declarant = models.ForeignKey(
        'Declarant',
        on_delete=models.DO_NOTHING,
        db_column='declarant_id',
        verbose_name='Юридическое лицо',
    )
    company = models.ForeignKey(
        'Company',
        on_delete=models.DO_NOTHING,
        db_column='personal_area_id',
        verbose_name='Сайт сетевой компании',
    )
    number = models.CharField(
        'Номер',
        max_length=255,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.number


class EnergyStatus(EnergyModel):
    name = models.CharField(
        'Статус',
        max_length=255,
    )
    created_at = models.DateTimeField(
        'Добавлено в',
        default=timezone.now,
        db_column='time_stamp',
    )
    date = models.DateField(
        'Дата статуса',
        db_column='status_time',
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Declarant(EnergyModel):
    name = models.CharField(
        'Юридическое лицо',
        db_column='name',
        max_length=255,
    )

    class Meta:
        db_table = 'declarant'
        verbose_name = 'юридическое лицо'
        verbose_name_plural = 'Юр. лица'
        managed = False

    def __str__(self):
        return self.name


class Company(EnergyModel):
    name = models.CharField(
        'Сайт',
        db_column='name',
        max_length=255,
    )
    link = models.CharField(
        'Ссылка на сайт',
        db_column='link',
        max_length=255,
    )

    class Meta:
        db_table = 'personal_areas'
        verbose_name = 'сетевая компания'
        verbose_name_plural = 'Сетевые компании'
        managed = False

    def __str__(self):
        return self.name


class Claim(EnergyRequest):
    number = models.CharField(
        'Номер заявки',
        db_column='claim_number',
        max_length=255
    )

    class Meta:
        db_table = 'claims'
        verbose_name = 'заявка'
        verbose_name_plural = 'Заявки'
        managed = False


class Appeal(EnergyRequest):
    number = models.CharField(
        'Номер обращения',
        db_column='message_number',
        max_length=255
    )

    class Meta:
        db_table = 'messages'
        verbose_name = 'обращение'
        verbose_name_plural = 'Обращения'
        managed = False


class ClaimStatus(EnergyStatus):
    claim = models.ForeignKey(
        Claim,
        on_delete=models.DO_NOTHING,
        db_column='claim_id',
        related_name='claim_statuses',
    )
    name = models.CharField(
        'Статус',
        db_column='claim_status',
        max_length=255,
    )

    class Meta:
        db_table = 'claims_states'
        verbose_name = 'статус заявки'
        verbose_name_plural = 'Статусы заявок'
        managed = False


class AppealStatus(EnergyStatus):
    appeal = models.ForeignKey(
        Appeal,
        on_delete=models.DO_NOTHING,
        db_column='message_id',
        related_name='appeal_statuses',
    )
    name = models.CharField(
        'Статус',
        db_column='message_status',
        max_length=255,
    )

    class Meta:
        db_table = 'messages_states'
        verbose_name = 'статус обращения'
        verbose_name_plural = 'Статусы обращений'
        managed = False


class AttrType(EnergyModel):
    attribute_id = models.IntegerField(
        'ID атрибута',
        db_column='constant_number',
        unique=True,
    )
    name = models.CharField(
        'Название',
        db_column='name',
        max_length=255,
    )
    description = models.CharField(
        'Описание',
        db_column='description',
        max_length=255,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'constant_types'
        verbose_name = 'тип атрибута'
        verbose_name_plural = 'Типы атрибутов'
        managed = False

    def __str__(self):
        return self.description or self.name


class ClaimAttr(EnergyAttr):
    claim = models.ForeignKey(
        Claim,
        on_delete=models.DO_NOTHING,
        db_column='claim_id',
        related_name='claim_attrs',
    )
    attr_type = models.ForeignKey(
        'AttrType',
        on_delete=models.DO_NOTHING,
        db_column='constant_type',
        to_field='attribute_id',
        related_name='claim_attrs',
    )

    class Meta:
        db_table = 'constants'
        verbose_name = 'атрибут заявки'
        verbose_name_plural = 'Атрибуты заявок'
        managed = False


class AppealAttr(EnergyAttr):
    appeal = models.ForeignKey(
        Appeal,
        on_delete=models.DO_NOTHING,
        db_column='message_id',
        related_name='appeal_attrs',
    )
    attr_type = models.ForeignKey(
        'AttrType',
        on_delete=models.DO_NOTHING,
        db_column='constant_type',
        to_field='attribute_id',
        related_name='appeal_attrs',
    )

    class Meta:
        db_table = 'messages_constants'
        verbose_name = 'атрибут обращения'
        verbose_name_plural = 'Атрибуты обращений'
        managed = False
