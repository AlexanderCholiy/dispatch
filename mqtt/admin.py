from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from mqtt.constants import (
    CELL_MEASSURE_PER_PAGE,
    CELL_PER_PAGE,
    DEVICE_PER_PAGE,
    OPERATOR_PER_PAGE,
)

from .models import Cell, CellMeasure, Device, Operator


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'mac_address',
        'sys_version',
        'app_version',
        'gps_lat',
        'gps_lon',
        'last_seen',
    )
    list_filter = ('sys_version', 'app_version')
    search_fields = ('mac_address',)
    readonly_fields = (
        'created_at', 'updated_at', 'last_seen', 'gps_lat', 'gps_lon', 'pole'
    )
    ordering = ('-created_at', 'id')
    autocomplete_fields = ('pole',)
    list_per_page = DEVICE_PER_PAGE

    fieldsets = (
        ('Основные данные', {
            'fields': ('mac_address', 'sys_version', 'app_version')
        }),
        ('Геолокация', {
            'fields': ('pole', 'gps_lat', 'gps_lon'),
            'classes': ('collapse',)
        }),
        ('Мета', {
            'fields': ('last_seen', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    list_filter = ('name',)
    search_fields = ('code', 'name')
    ordering = ('name', 'id')
    list_per_page = OPERATOR_PER_PAGE

    def has_delete_permission(self, request, obj=None):
        """Запрещает удаление операторов, операция может быть тяжелой."""
        return False


@admin.register(Cell)
class CellAdmin(admin.ModelAdmin):
    list_display = (
        'cell_id',
        'operator_link',
        'rat',
        'freq',
        'lac',
        'pci_psc_bsic',
    )
    list_filter = ('rat', 'operator__name',)
    search_fields = ('cell_id', 'operator__code',)
    readonly_fields = ('created_at', 'updated_at',)
    autocomplete_fields = ('operator',)
    list_per_page = CELL_PER_PAGE

    fieldsets = (
        ('Идентификаторы', {
            'fields': ('cell_id', 'operator', 'rat', 'lac',)
        }),
        ('Параметры сети', {
            'fields': ('freq',),
        }),
        ('Коды идентификации (PCI/PSC/BSIC)', {
            'fields': ('pci', 'psc', 'bsic'),
            'description': (
                'Заполняйте только соответствующие поля для типа сети'
            )
        }),
        ('Мета', {
            'fields': ('last_seen', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def operator_link(self, obj):
        if not obj.operator:
            return '-'
        url = reverse('admin:mqtt_operator_change', args=[obj.operator.pk])
        return format_html(
            '<a href="{}" target="_blank">{}</a>', url, str(obj.operator)
        )
    operator_link.short_description = 'Оператор'
    operator_link.admin_order_field = 'operator'

    def pci_psc_bsic(self, obj):
        parts = []
        if obj.pci:
            parts.append(f'PCI: {obj.pci}')
        if obj.psc:
            parts.append(f'PSC: {obj.psc}')
        if obj.bsic:
            parts.append(f'BSIC: {obj.bsic}')
        return ', '.join(parts) if parts else '-'
    pci_psc_bsic.short_description = 'Коды БС'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('operator')


@admin.register(CellMeasure)
class CellMeasureAdmin(admin.ModelAdmin):
    list_display = (
        'event_datetime',
        'device_link',
        'cell_link',
        'signal_strength',
        'rat_display',
    )
    list_filter = ('cell__rat', 'cell__operator__name')
    search_fields = ('device__mac_address', 'cell__cell_id')
    date_hierarchy = 'event_datetime'
    list_per_page = CELL_MEASSURE_PER_PAGE
    readonly_fields = ('event_datetime', 'mongo_id',)

    autocomplete_fields = ('device', 'cell')

    fieldsets = (
        ('Контекст измерения', {
            'fields': ('device', 'cell', 'cba', 'index')
        }),
        ('Показатели сигнала', {
            'fields': (
                ('rsrp', 'rsrq'),
                ('rscp', 'ecno'),
                ('rssi', 'rxlev', 'c1')
            ),
            'classes': ('collapse',)
        }),
        ('Мета', {
            'fields': ('event_datetime', 'mongo_id',),
            'classes': ('collapse',)
        }),
    )

    def device_link(self, obj):
        if not obj.device:
            return '-'
        url = reverse('admin:mqtt_device_change', args=[obj.device.pk])
        return format_html(
            '<a href="{}" target="_blank">{}</a>', url, str(obj.device)
        )
    device_link.short_description = 'Устройство'
    device_link.admin_order_field = 'device'

    def cell_link(self, obj):
        url = reverse('admin:mqtt_cell_change', args=[obj.cell.pk])
        return format_html(
            '<a href="{}" target="_blank">{}</a>', url, obj.cell
        )
    cell_link.short_description = 'Сота'
    cell_link.admin_order_field = 'cell'

    def signal_strength(self, obj):
        val = obj.rsrp or obj.rscp or obj.rssi or obj.rxlev
        if val is None:
            return 'N/A'

        color = (
            '#d9534f'
            if val < -90
            else ('#f0ad4e' if val < -70 else '#5cb85c')
        )
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            f'{val} dBm'
        )
    signal_strength.short_description = 'Уровень сигнала'

    def rat_display(self, obj):
        return obj.cell.rat
    rat_display.short_description = 'RAT'
    rat_display.admin_order_field = 'cell__rat'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('device', 'cell')
