from django.contrib.gis.db.models import GeometryField
from django.db import models


class ModemLevel(models.Model):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='Value',
    )
    description = models.TextField(
        'Описание',
        null=True,
        blank=True,
        db_column='Description',
    )

    class Meta:
        db_table = 'ModemLevelEnumDescription'
        verbose_name = 'тип устройства'
        verbose_name_plural = 'Типы устройств'
        managed = False

    def __str__(self):
        description = self.description or 'Unknown'
        return f'{description} (ID: {self.id})'


class Status(models.Model):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='Status',
    )
    level = models.TextField(
        'Уровень',
        null=True,
        blank=True,
        db_column='Level',
    )
    description = models.TextField(
        'Описание',
        null=True,
        blank=True,
        db_column='Description',
    )
    st_type = models.TextField(
        'Тип',
        null=True,
        blank=True,
        db_column='Type',
    )
    level_description = models.TextField(
        'Статус',
        null=True,
        blank=True,
        db_column='LevelDescription',
    )

    class Meta:
        abstract = True

    def __str__(self):
        description = self.level_description or 'Unknown'
        return f'{description} (ID: {self.id})'


class ModemStatus(Status):

    class Meta:
        db_table = 'ModemStatuses'
        verbose_name = 'статус модема'
        verbose_name_plural = 'Статусы модемов'
        managed = False


class PoleStatus(Status):

    class Meta:
        db_table = 'SiteStatuses'
        verbose_name = 'статус опоры'
        verbose_name_plural = 'Статусы опор'
        managed = False


class ModemState(models.IntegerChoices):
    IN_USE = (0, 'В эксплуатации')
    REPAIR = (1, 'В ремонте')
    REMOVED = (2, 'Демонтирован')


class Modem(models.Model):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='Id',
    )
    ip = models.TextField(
        'IP адрес сим карты',
        db_column='IP',
    )
    level = models.ForeignKey(
        ModemLevel,
        on_delete=models.DO_NOTHING,
        verbose_name='Тип устройства',
        db_column='Level',
    )
    status = models.ForeignKey(
        ModemStatus,
        on_delete=models.DO_NOTHING,
        verbose_name='Статус',
        db_column='Status',
    )
    slate = models.IntegerField(
        'Состояние модема',
        db_column='ModemState',
        default=ModemState.IN_USE,
        choices=ModemState.choices
    )
    created_at = models.DateTimeField(
        'Добавлено в',
        null=True,
        blank=True,
        db_column='AlarmTime',
    )
    last_data_at = models.DateTimeField(
        'Дата последних показаний',
        null=True,
        blank=True,
        db_column='LastReceivedDate',
    )
    mac = models.TextField(
        'MAC адрес',
        null=True,
        blank=True,
        db_column='MAC',
    )
    serial = models.TextField(
        'Номер контроллера',
        null=True,
        blank=True,
        db_column='Serial',
    )
    version = models.TextField(
        'Версия контроллера',
        null=True,
        blank=True,
        db_column='HardwareVersion',
    )
    firmware = models.TextField(
        'Версия прошивки контроллера',
        null=True,
        blank=True,
        db_column='Firmware',
    )
    cabinet = models.TextField(
        'Номер шкафа',
        null=True,
        blank=True,
        db_column='CabinetSerial',
    )
    coordinates = GeometryField(
        'Координаты устройства',
        null=True,
        blank=True,
        db_column='Coordinates',
    )

    class Meta:
        db_table = 'Modems'
        verbose_name = 'оборудование мониторинга'
        verbose_name_plural = 'Оборудование мониторинга'

    def __str__(self):
        cabinet = self.cabinet or 'Unknown'
        return f'{self.ip} ({cabinet})'


class Pole(models.Model):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='id',
    )
    site_id = models.BigIntegerField(
        'ID опоры в TS',
        null=True,
        blank=True,
        db_column='ExternalId',
    )
    pole = models.TextField(
        'Шифр опоры',
        db_column='Ref',
    )
    address = models.TextField(
        'Адрес',
        null=True,
        blank=True,
        db_column='Address',
    )
    coordinates = GeometryField(
        'Координаты опоры',
        null=True,
        blank=True,
        db_column='Coordinates',
    )
    ts_status = models.TextField(
        'Статус в TS',
        null=True,
        blank=True,
        db_column='TSStatus',
    )
    status = models.ForeignKey(
        PoleStatus,
        on_delete=models.DO_NOTHING,
        verbose_name='Статус',
        db_column='Status',
    )

    class Meta:
        db_table = 'Sites'
        verbose_name = 'опора'
        verbose_name_plural = 'Опоры'

    def __str__(self):
        return self.pole


class ModemPoleRealtion(models.Model):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='id',
    )
    modem_id = models.ForeignKey(
        Modem,
        on_delete=models.CASCADE,
        verbose_name='Устройство',
        db_column='ModemId',
    )
    pole_id = models.ForeignKey(
        Pole,
        on_delete=models.CASCADE,
        verbose_name='Опора',
        db_column='SiteId',
    )
    dismantled = models.BooleanField(
        'Был ли демонтаж',
        db_column='Dismantled',
        default=False,
    )
    dismantled_at = models.DateTimeField(
        'Демонтировано в',
        null=True,
        blank=True,
        db_column='DismantledAt',
    )

    class Meta:
        db_table = 'ModemSites'
        verbose_name = 'связь опоры с устройством'
        verbose_name_plural = 'Связи опор с устройствами'

    def __str__(self):
        return f'Опора {self.pole_id} - утсройство {self.modem_id}'


class ModemNotification(models.Model):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='id',
    )
    modem = models.ForeignKey(
        Modem,
        on_delete=models.CASCADE,
        verbose_name='Устройство',
        db_column='ModemId',
    )
    action = models.TextField(
        'Действие',
        db_column='Key',
    )
    sent_at = models.DateTimeField(
        'Отправлено в',
        db_column='Sent',
    )

    class Meta:
        db_table = 'ModemNotifications'
        verbose_name = 'уведомление от устройства'
        verbose_name_plural = 'Уведомления от устройств'

    def __str__(self):
        sent_at = self.sent_at.strftime('%d.%m.%Y %H:%M:%S')
        return f'{self.modem} - {self.action} ({sent_at})'
