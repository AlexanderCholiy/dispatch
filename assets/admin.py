from django.contrib import admin
from django.core.cache import cache

from assets.constants import (
    CACHE_KEY_ASSETS_STATUS_PREFIX,
    MAX_EXUIPMENT_PER_PAGE,
)
from assets.models import Equipment
from core.constants import EMPTY_VALUE

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_per_page = MAX_EXUIPMENT_PER_PAGE

    list_display = (
        'modem_ip',
        'modem_mac',
        'status_cache',
        'comment',
        'is_active',
    )

    search_fields = ('modem_ip', 'modem_mac', 'comment')
    list_editable = ('comment', 'is_active')
    ordering = ('created_at', 'modem_ip', 'modem_mac')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('created_at', 'status_card')

    fieldsets = (
        (None, {
            'fields': ('modem_ip', 'modem_mac'),
        }),
        ('Мета', {
            'classes': ('collapse',),
            'fields': ('is_active', 'comment', 'status_card', 'created_at'),
        }),
    )

    def status_cache(self, obj):
        """Отображение в списке"""
        return self._get_status_text(obj)

    status_cache.short_description = 'Текущее состояние'
    status_cache.admin_order_field = ''

    def status_card(self, obj):
        """Отображение в карточке (форме)"""
        return self._get_status_text(obj)

    status_card.short_description = 'Текущее состояние'
    status_card.admin_order_field = ''

    def _get_status_text(self, obj):
        """Внутренний метод для получения текста статуса"""
        if not obj or not obj.modem_ip or not obj.modem_mac:
            return '-'

        ip = obj.modem_ip.strip()
        mac = obj.modem_mac.upper().strip()
        cache_key = f"{CACHE_KEY_ASSETS_STATUS_PREFIX}{ip}:{mac}"

        status_msg = cache.get(cache_key)

        if not status_msg:
            return 'Нет данных о проверке'

        return status_msg
