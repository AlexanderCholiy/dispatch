from django.db import models

from core.constants import MAX_LG_DESCRIPTION, MAX_ST_DESCRIPTION
from emails.constants import MAX_EMAIL_LEN

from .constants import (
    MAX_PHONE_LEN, MAX_POLE_LEN, UNDEFINED_CASE, UNDEFINED_ID
)


def get_default_contractor():
    contractor, _ = AVRContractor.objects.get_or_create(
        contractor_name=UNDEFINED_CASE,
        defaults={'is_excluded_from_contract': False}
    )
    return contractor.pk


class ContractorEmail(models.Model):
    """Email адрес подрядчика."""
    email = models.EmailField(
        'email',
        max_length=MAX_EMAIL_LEN,
        unique=True,
        db_index=True,
    )

    class Meta:
        verbose_name = 'Email подрядчика'
        verbose_name_plural = 'Email подрядчиков'

    def __str__(self):
        return self.email


class ContractorPhone(models.Model):
    """Телефон подрядчика."""
    phone = models.CharField(
        'Телефон',
        max_length=MAX_PHONE_LEN,
        unique=True,
        db_index=True,
    )

    class Meta:
        verbose_name = 'Телефон подрядчика'
        verbose_name_plural = 'Телефоны подрядчиков'

    def __str__(self):
        return self.phone


class AVRContractor(models.Model):
    """Подрядчики ответственные за выполнение АВР на опорах."""
    contractor_name = models.CharField(
        'Подрядчик',
        max_length=MAX_ST_DESCRIPTION,
        unique=True,
    )
    is_excluded_from_contract = models.BooleanField('Исключен из договора')
    emails = models.ManyToManyField(
        ContractorEmail,
        blank=True,
        related_name='contractors',
        verbose_name='Emails',
    )
    phones = models.ManyToManyField(
        ContractorPhone,
        blank=True,
        related_name='contractors',
        verbose_name='Телефоны',
    )

    class Meta:
        verbose_name = 'подрядчик по АВР'
        verbose_name_plural = 'Подрядчики по АВР'

    def __str__(self):
        return self.contractor_name


class Pole(models.Model):
    """Модель опоры TowerStore."""
    site_id = models.IntegerField(
        unique=True,
        null=False,
        verbose_name='ID опоры в TS'
    )
    pole = models.CharField(
        max_length=MAX_POLE_LEN,
        null=False,
        verbose_name='Шифр опоры',
        db_index=True,
    )
    bs_name = models.CharField(
        max_length=MAX_ST_DESCRIPTION,
        null=False,
        verbose_name='Базовая станция',
        db_index=True,
    )
    pole_status = models.CharField(
        max_length=MAX_ST_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Статус опоры'
    )
    pole_latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Широта опоры'
    )
    pole_longtitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Долгота опоры'
    )
    pole_height = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Высота опоры'
    )
    region = models.CharField(
        max_length=MAX_ST_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Регион'
    )
    address = models.CharField(
        max_length=MAX_LG_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Адрес'
    )
    infrastructure_company = models.CharField(
        max_length=MAX_ST_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Инфраструктурная компания'
    )
    anchor_operator = models.CharField(
        max_length=MAX_ST_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Якорный оператор'
    )
    avr_contractor = models.ForeignKey(
        'AVRContractor',
        on_delete=models.SET_DEFAULT,
        default=get_default_contractor,
        related_name='poles',
        verbose_name='Подрядчик по АВР',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['pole', 'bs_name'],
                name='unique_pole_ts'
            )
        ]
        verbose_name = 'опора TS'
        verbose_name_plural = 'Опоры TowerStore'

    @staticmethod
    def add_default_value():
        pole, _ = Pole.objects.get_or_create(
            site_id=UNDEFINED_ID,
            defaults={
                'pole': UNDEFINED_CASE,
                'bs_name': UNDEFINED_CASE,
                'pole_status': None,
                'pole_latitude': None,
                'pole_longtitude': None,
                'pole_height': None,
                'region': None,
                'address': None,
                'infrastructure_company': None,
                'anchor_operator': None,
            },
        )
        return pole

    def __str__(self):
        return self.pole


class BaseStation(models.Model):
    """Базовые станции/оборудование."""
    bs_name = models.CharField(
        'Имя БС / оборудования',
        max_length=MAX_ST_DESCRIPTION,
        null=False,
        db_index=True
    )
    pole = models.ForeignKey(
        Pole,
        on_delete=models.CASCADE,
        related_name='base_stations',
        verbose_name='Связанная опора',
        db_index=True,
    )
    operator = models.ManyToManyField(
        'BaseStationOperator',
        related_name='base_stations',
        verbose_name='Операторы',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['pole', 'bs_name',],
                name='unique_base_station_ts'
            )
        ]
        verbose_name = 'базовая станция'
        verbose_name_plural = 'Базовые станции'

    def __str__(self):
        return self.bs_name


class BaseStationOperator(models.Model):
    """Операторы привязанные к базовым станциям."""
    operator_name = models.CharField(
        'Оператор',
        max_length=MAX_ST_DESCRIPTION,
    )
    operator_group = models.CharField(
        'Группа операторов',
        max_length=MAX_ST_DESCRIPTION,
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['operator_name', 'operator_group'],
                name='unique_operator_ts'
            )
        ]
        verbose_name = 'оператор БС'
        verbose_name_plural = 'Операторы на БС'

    def __str__(self):
        return self.operator_name
