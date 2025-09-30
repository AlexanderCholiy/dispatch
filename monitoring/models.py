from django.db import models

from core.models_readonly import ReadOnlyModel


class DeviceTypes(models.IntegerChoices):
    HU = (0, 'ЩУ')
    OLD_RHU = (1, 'Старый РЩУ')
    RHU = (2, 'РЩУ')
    RH = (3, 'РЩ')
    HKF = (4, 'ЩКФ')
    HUM = (5, 'ЩУМ')
    DGU_HKG = (6, 'ДГУ (ЩКГ)')
    HU_NEVA = (7, 'ЩУ Нева')
    HU_IRZ = (48, 'ЩУ IRZ')
    RHU_IRZ = (49, 'РЩУ IRZ')
    HU_TELEOFIS = (50, 'ЩУ Teleofis')
    RHU_TELEOFIS = (51, 'РЩУ Teleofis')
    HU_MERKURIY_RB = (60, 'ЩУ Меркурий РБ')
    RHU_MERKURIY_RB = (61, 'РЩУ Меркурий РБ')
    HU_PSH_RB = (70, 'ЩУ ПСЧ РБ')
    ENTEK_RB = (81, 'Энтек РБ')
    RHU_NEW = (102, 'RHU NEW')
    RH_NEW = (103, 'RH NEW')
    HU_NEVA_NEW = (107, 'ЩУ Нева NEW')


class MSysStatus(ReadOnlyModel):
    id = models.BigIntegerField(
        primary_key=True,
        db_column='StatusID',
    )
    description = models.CharField(
        'Описание',
        max_length=255,
        null=True,
        blank=True,
        db_column='StatusDesc',
    )

    class Meta:
        db_table = 'MSys_Statuses'
        verbose_name = 'статус мониторинга'
        verbose_name_plural = 'Статусы Мониторинга'

    def __str__(self):
        return str(self.id)


class MSysPoles(ReadOnlyModel):
    pole = models.CharField(
        'Шифр опоры',
        primary_key=True,
        db_column='PoleID',
        max_length=20,
    )
    status = models.ForeignKey(
        MSysStatus,
        on_delete=models.DO_NOTHING,
        verbose_name='Статус',
        related_name='pole',
        db_column='PoleStatus',
    )

    class Meta:
        db_table = 'MSys_Poles'
        verbose_name = 'опора мониторинга'
        verbose_name_plural = 'Опоры Мониторинга'

    def __str__(self):
        return self.pole


class MSysModem(ReadOnlyModel):
    modem_ip = models.CharField(
        'IP адрес сим карты',
        primary_key=True,
        db_column='ModemID',
        max_length=40,
    )
    level = models.IntegerField(
        'Тип устройства',
        db_column='ModemLevel',
        choices=DeviceTypes.choices,
    )
    status = models.ForeignKey(
        MSysStatus,
        on_delete=models.DO_NOTHING,
        verbose_name='Статус',
        related_name='modem',
        db_column='ModemStatus',
    )
    pole_1 = models.ForeignKey(
        MSysPoles,
        on_delete=models.DO_NOTHING,
        verbose_name='Первая опора',
        related_name='modem_pole_1',
        db_column='ModemPole'
    )
    pole_2 = models.ForeignKey(
        MSysPoles,
        on_delete=models.DO_NOTHING,
        verbose_name='Вторая опора',
        related_name='modem_pole_2',
        db_column='ModemPole2',
    )
    pole_3 = models.ForeignKey(
        MSysPoles,
        on_delete=models.DO_NOTHING,
        verbose_name='Третья опора',
        related_name='modem_pole_3',
        db_column='ModemPole3',
    )
    updated_at = models.DateTimeField(
        'Обновлено в',
        null=True,
        blank=True,
        db_column='ModemAlarmtimestamp',
    )
    modem_mac = models.CharField(
        'MAC адрес',
        db_column='ModemCounter',
        max_length=30,
        null=True,
        blank=True,
    )
    modem_phone = models.CharField(
        'Телефон',
        db_column='ModemMsisdn',
        max_length=20,
        null=True,
        blank=True,
    )
    modem_serial = models.CharField(
        'Номер контроллера',
        db_column='ModemSerial',
        max_length=30,
        null=True,
        blank=True,
    )
    modem_number = models.CharField(
        'Серийный номер сим карты',
        db_column='ModemIMSI',
        max_length=20,
        null=True,
        blank=True,
    )
    cabinet = models.CharField(
        'Номер шкафа',
        db_column='ModemCabinetSerial',
        max_length=30,
        null=True,
        blank=True,
    )
    modem_latitude = models.FloatField(
        'Широта устройства',
        db_column='ModemLatitude',
        max_length=12,
        null=True,
        blank=True,
    )
    modem_longtitude = models.CharField(
        'Долгота устройства',
        db_column='ModemLongtitude',
        max_length=15,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'MSys_Modems'
        verbose_name = 'оборудование мониторинга'
        verbose_name_plural = 'Оборудование Мониторинга'

    def __str__(self):
        return self.modem_ip
