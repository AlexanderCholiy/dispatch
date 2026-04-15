from django.db import models
from django.utils import timezone

from mqtt.constants import (
    MAX_DEVICE_VERSION_LEN,
    MAX_MAC_LEN,
    MAX_NETWORK_TYPE_LEN,
    MAX_OPERATOR_CODE_LEN,
    MAX_OPERATOR_NAME_LEN,
)
from ts.models import Pole


class NetworkType(models.TextChoices):
    GSM = ('2G', 'GSM (2G)')
    UMTS = ('3G', 'UMTS (3G)')
    LTE = ('4G', 'LTE (4G)')


class Device(models.Model):
    mac_address = models.CharField(
        max_length=MAX_MAC_LEN,
        unique=True,
        verbose_name='MAC адрес контроллера',
    )
    gps_lat = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Широта',
    )
    gps_lon = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Долгота',
    )
    sys_version = models.CharField(
        max_length=MAX_DEVICE_VERSION_LEN,
        null=True,
        blank=True,
        verbose_name='Версия контроллера',
    )
    app_version = models.CharField(
        max_length=MAX_DEVICE_VERSION_LEN,
        null=True,
        blank=True,
        verbose_name='Версия прошивки',
    )
    last_seen = models.DateTimeField(
        db_index=True,
        default=timezone.now,
        verbose_name='Дата и время последнего события',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления',
    )
    pole = models.ForeignKey(
        Pole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Опора',
        related_name='devices'
    )

    class Meta:
        verbose_name = 'устройство'
        verbose_name_plural = 'Устройства'
        indexes = [
            models.Index(fields=['mac_address', '-last_seen']),
            models.Index(fields=['gps_lat', 'gps_lon']),
        ]

    def __str__(self):
        return f'MAC: {self.mac_address}'


class Operator(models.Model):
    code = models.CharField(
        max_length=MAX_OPERATOR_CODE_LEN,
        unique=True,
        verbose_name='Код оператора (MNC+MCC)',
    )
    name = models.CharField(
        max_length=MAX_OPERATOR_NAME_LEN,
        null=True,
        blank=True,
        verbose_name='Имя оператора',
    )

    class Meta:
        verbose_name = 'оператор связи'
        verbose_name_plural = 'Операторы связи'
        ordering = ('name', 'id')

    def __str__(self):
        return f'{self.code} ({self.name or "N/A"})'


class Cell(models.Model):
    cell_id = models.PositiveBigIntegerField(
        db_index=True,
        verbose_name='Cell ID',
    )
    operator = models.ForeignKey(
        Operator,
        db_index=True,
        on_delete=models.CASCADE,
        related_name='cells',
        verbose_name='Оператор',
    )
    rat = models.CharField(
        max_length=MAX_NETWORK_TYPE_LEN,
        choices=NetworkType.choices,
        verbose_name='Тип сети',
    )
    lac = models.PositiveIntegerField(
        verbose_name='LAC (2G/3G) / TAC (4G)',
        help_text=(
            '- LAC (Location Area Code) /  TAC (Tracking Area Code) - '
            'идентификаторы групп базовых станций'
        ),
    )
    freq = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Номер частотного канала',
        help_text=(
            'Arfcn or Uarfcn or Earfcn - Абсолютный номер частотного канала '
            'в зависимости от типа сети'
        ),
    )
    pci = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='PCI',
        help_text=(
            'PCI (Physical Cell ID) — идентификатор базовой станции в сетях '
            '4G'
        ),
    )
    psc = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='PSC',
        help_text=(
            'PSC (Primary Scrambling Code) - идентификатор базовой станции '
            'в сетях 3G'
        ),
    )
    bsic = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='BSIC',
        help_text=(
            'BSIC (Base station ID code) - идентификатор базовой станции '
            'в сетях 2G'
        ),
    )
    last_seen = models.DateTimeField(
        db_index=True,
        default=timezone.now,
        verbose_name='Дата и время последнего события',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления',
    )

    class Meta:
        verbose_name = 'сота'
        verbose_name_plural = 'Соты'
        ordering = ['-last_seen', '-cell_id', 'operator']
        indexes = [
            models.Index(
                fields=['operator', 'rat', 'lac', 'cell_id'],
                name='idx_cell_full_lookup',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['operator', 'rat', 'lac', 'cell_id'],
                name='unique_cell_per_operator_rat_lac',
            ),
        ]

    def __str__(self):
        return (
            f'{self.operator.name or self.operator.code} | '
            f'{self.rat} | '
            f'LAC/TAC:{self.lac} | '
            f'Cell:{self.cell_id}'
        )


class CellMeasure(models.Model):
    cell = models.ForeignKey(
        Cell,
        on_delete=models.CASCADE,
        related_name='measurements',
        verbose_name='Сота',
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='measurements',
        verbose_name='Устройство',
    )
    index = models.PositiveSmallIntegerField(
        verbose_name='Индекс соты в списке',
    )
    cba = models.BooleanField(
        null=True,
        blank=True,
        verbose_name='Запрет доступа к соте',
        help_text=(
            'Cell Bar indicator (TRUE=доступ запрещен, FALSE=доступ разрешен)'
        )
    )
    event_datetime = models.DateTimeField(
        db_index=True,
        default=timezone.now,
        verbose_name='Время регистрации',
    )

    # LTE (4G)
    rsrp = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name='RSRP (dBm)',
        help_text=(
            'RSRP (Reference Signal Received Power) - уровень сигнала 4G',
        ),
    )
    rsrq = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name='RSRQ (dB)',
        help_text=(
            'RSRQ (Reference Signal Received Quality) - качество сигнала 4G',
        ),
    )

    # UMTS (3G)
    rscp = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name='RSCP (dBm)',
        help_text='RSCP (Received signal Code power) - уровень сигнала 3G',
    )
    ecno = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Ec/No (dB)',
        help_text=(
            'Ec/No (Ratio of energy per modulating bit to the noise spectral '
            'density) - качество сигнала 3G'
        ),
    )

    # GSM (2G)
    rssi = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name='RSSI (dBm)',
        help_text=(
            'RSSI (Received Signal Strength Indicator) - уровень сигнала 2G'
        ),
    )
    rxlev = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name='RXLEV',
        help_text=(
            'RXLEV (Received Signal Level) - показатель мощности '
            'радиосигнала в сетях 2G'
        ),
    )
    c1 = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name='C1',
        help_text=(
            'C1 (Cell selection criterion) - критерий «пригодности» сигнала '
            'для работы в сетях 2G'
        ),
    )

    class Meta:
        verbose_name = 'показание соты'
        verbose_name_plural = 'Показания сот'
        ordering = [
            '-event_datetime',
            'cell',
            'device',
            '-rsrp',
            '-rscp',
            '-rssi',
            'id',
        ]
        indexes = [
            models.Index(
                fields=['device', '-event_datetime'],
                name='idx_device_event_desc',
            ),
            models.Index(
                fields=['cell', '-event_datetime'],
                name='idx_cell_event_desc',
            ),
            models.Index(
                fields=['device', 'cell'],
                name='idx_device_cell',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'cell', 'event_datetime'],
                name='unique_device_cell'
            ),
        ]

    def __str__(self):
        sig = self.rsrp or self.rscp or self.rssi or self.rxlev or 'NaN'
        return f'{self.event_datetime.strftime("%Y-%m-%d %H:%M")}: {sig} dBm'
