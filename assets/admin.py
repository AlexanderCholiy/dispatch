from django.contrib import admin

from assets.constants import MAX_EXUIPMENT_PER_PAGE
from assets.models import Equipment
from core.constants import EMPTY_VALUE

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_per_page = MAX_EXUIPMENT_PER_PAGE
    list_display = (
        'modem_ip',
        'modem_mac',
        'comment',
        'is_active',
    )
    search_fields = (
        'modem_ip',
        'modem_mac',
        'comment',
    )
    list_editable = ('comment', 'is_active')
    ordering = ('created_at', 'modem_ip', 'modem_mac')
    list_filter = (
        'is_active',
        'created_at',
    )
    readonly_fields = ('created_at',)

    fieldsets = (
        (None, {
            'fields': ('modem_ip', 'modem_mac',)
        }),
        ('Мета', {
            'classes': ('collapse',),
            'fields': ('comment', 'is_active', 'created_at'),
        }),
    )
