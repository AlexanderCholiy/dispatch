from django.db import models

from assets.constants import MODEM_MAC_MAX_LEN
from assets.validators import mac_validator


class Equipment(models.Model):
    modem_ip = models.GenericIPAddressField(
        'IP адрес сим карты',
        protocol='both',
        unpack_ipv4=False,
    )
    modem_mac = models.CharField(
        'MAC-адрес',
        max_length=MODEM_MAC_MAX_LEN,
        validators=[mac_validator],
    )
    comment = models.TextField(
        'Комментарий',
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(
        'Активно',
        default=True,
        db_index=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления',
        db_index=True,
    )

    class Meta:
        verbose_name = 'АО'
        verbose_name_plural = 'Активное оборудование'

        constraints = [
            models.UniqueConstraint(
                fields=['modem_ip', 'modem_mac'],
                name='unique_modem_ip_mac'
            )
        ]

    def save(self, *args, **kwargs):
        self.modem_mac = self.modem_mac.upper()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.modem_ip
