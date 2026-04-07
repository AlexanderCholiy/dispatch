from django.db import models
from django.utils import timezone

from mqtt.constants import (
    MAX_DEVICE_VERSION_LEN,
    MAX_MAC_LEN,
    MAX_MCC_MNC_LEN,
    MAX_NETWORK_TYPE_LEN,
    MAX_OPERATOR_CODE_LEN,
    MAX_OPERATOR_NAME_LEN,
)


class NetworkType(models.TextChoices):
    GSM = ('2G', 'GSM (2G)')
    UMTS = ('3G', 'UMTS (3G)')
    LTE = ('4G', 'LTE (4G)')
    NR = ('5G', 'NR (5G)')


class OperatorStatus(models.IntegerChoices):
    FORBIDDEN = (0, 'Forbidden (Запрещена)')
    CURRENT = (1, 'Current (Выбрана)')
    AVAILABLE = (2, 'Available (Доступна)')
    HOME = (3, 'Home (Домашняя)')


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

    class Meta:
        verbose_name = 'устройство'
        verbose_name_plural = 'Устройства'
        indexes = [
            models.Index(fields=['mac_address', '-last_seen']),
            models.Index(fields=['gps_lat', 'gps_lon']),
        ]

    def __str__(self):
        return f'MAC: {self.mac_address}'


class CellInfo(models.Model):
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='cells',
        verbose_name='Устройство',
    )
    index = models.PositiveSmallIntegerField(
        verbose_name='Индекс соты в списке',
    )
    cell_id = models.PositiveBigIntegerField(
        db_index=True,
        verbose_name='Cell ID',
    )
    event_datetime = models.DateTimeField(
        db_index=True,
        default=timezone.now,
        verbose_name='Время регистрации',
    )
    mcc_mnc = models.CharField(
        max_length=MAX_MCC_MNC_LEN,
        null=True,
        blank=True,
        verbose_name='MCC-MNC код оператора',
    )
    network_type = models.CharField(
        max_length=MAX_NETWORK_TYPE_LEN,
        choices=NetworkType.choices,
        null=True,
        blank=True,
        verbose_name='Тип сети',
    )

    # Общие параметры
    freq = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Частота',
    )
    tac = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='TAC (4G)',
        help_text=(
            'TAC (Tracking Area Code) - идентификаторы групп базовых станций '
            'в сотовой связи 4G'
        ),
    )
    lac = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='LAC (2G/3G)',
        help_text=(
            'LAC (Location Area Code) - идентификаторы групп базовых станций '
            'в сотовой связи 2G и 3G'
        ),
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
        verbose_name="RSRQ (dB)",
        help_text=(
            'RSRQ (Reference Signal Received Quality) - качество сигнала 4G',
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
    earfcn = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='EARFCN',
        help_text=(
            'EARFCN (E-UTRA Absolute Radio Frequency Channel Number) - '
            'уникальный номер частоты для 4G'
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
    psc = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='PSC',
        help_text=(
            'PSC (Primary Scrambling Code) - идентификатор базовой станции '
            'в сетях 3G'
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
    bsic = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='BSIC',
        help_text=(
            'BSIC (Base station ID code) - идентификатор базовой станции '
            'в сетях 2G'
        ),
    )

    class Meta:
        verbose_name = 'данные соты'
        verbose_name_plural = 'Данные сот'
        ordering = [
            '-event_datetime', 'device', '-rsrp', '-rscp', '-rssi', 'id'
        ]
        indexes = [
            models.Index(fields=['device', 'cell_id']),
            models.Index(fields=['network_type', 'rsrp']),
            models.Index(fields=['network_type', 'rscp']),
            models.Index(fields=['network_type', 'rssi']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'cell_id', 'event_datetime'],
                name='unique_device_cell'
            ),
        ]

    def __str__(self):
        sig = self.rsrp or self.rscp or self.rssi or self.rxlev or 'NaN'
        return f'Сота {self.cell_id} ({self.network_type}): {sig} dBm'


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


class DeviceOperator(models.Model):
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='operators',
        verbose_name='Устройство'
    )
    operator = models.ForeignKey(
        Operator,
        on_delete=models.CASCADE,
        related_name='seen_by_devices',
        verbose_name='Оператор',
    )
    index = models.PositiveIntegerField(
        verbose_name='Индекс в списке',
    )
    status = models.PositiveSmallIntegerField(
        choices=OperatorStatus.choices,
        null=True,
        blank=True,
        verbose_name='Статус',
    )
    last_seen = models.DateTimeField(
        db_index=True,
        default=timezone.now,
        verbose_name='Видел последний раз',
    )

    class Meta:
        verbose_name = 'видимый оператор'
        verbose_name_plural = 'Видимые операторы'
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'operator',],
                name='unique_device_operator_pair'
            ),
        ]
        ordering = ('-last_seen', 'id')

    def __str__(self):
        status_label = self.get_status_display() if self.status else 'Unknown'
        return (
            f'{self.device} - {self.operator}: {status_label}'
        )
