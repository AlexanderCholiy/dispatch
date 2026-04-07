from django.contrib import admin

from mqtt.constants import (
    CELL_INFO_PER_PAGE,
    DEVICE_OPERATOR_PER_PAGE,
    DEVICE_PER_PAGE,
    OPERATOR_PER_PAGE,
)
from mqtt.models import CellInfo, Device, DeviceOperator, Operator


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        'mac_address',
        'last_seen',
        'gps_lat',
        'gps_lon',
        'sys_version',
        'app_version',
    )
    list_filter = ('sys_version', 'app_version')
    search_fields = ('mac_address',)
    readonly_fields = ('created_at', 'updated_at', 'last_seen')
    date_hierarchy = 'last_seen'  # Навигация по дате сверху
    list_per_page = DEVICE_PER_PAGE

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'mac_address',
                'sys_version',
                'app_version',
            )
        }),
        ('GPS координаты', {
            'fields': ('gps_lat', 'gps_lon'),
            'classes': ('collapse',)
        }),
        ('Системные поля', {
            'fields': ('created_at', 'updated_at', 'last_seen'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CellInfo)
class CellInfoAdmin(admin.ModelAdmin):
    list_display = (
        'cell_id',
        'network_type',
        'rsrp',
        'rscp',
        'rssi',
        'rxlev',
        'freq',
        'tac',
        'lac',
        'event_datetime',
        'device_link',
    )
    list_filter = ('network_type', 'event_datetime')
    search_fields = ('cell_id', 'mcc_mnc', 'device__mac_address')
    autocomplete_fields = ('device',)
    list_per_page = CELL_INFO_PER_PAGE

    def device_link(self, obj: CellInfo):
        if obj.device:
            return str(obj.device)
        return '-'

    device_link.short_description = 'Устройство'
    device_link.admin_order_field = 'device'

    fieldsets = (
        ('Идентификация', {
            'fields': (
                'index',
                'cell_id',
                'mcc_mnc',
                'network_type',
                'freq',
                'event_datetime',
            )
        }),
        ('Параметры сети (4G)', {
            'fields': ('tac', 'rsrp', 'rsrq', 'pci', 'earfcn'),
            'classes': ('collapse',)
        }),
        ('Параметры сети (3G)', {
            'fields': ('lac', 'rscp', 'ecno', 'psc'),
            'classes': ('collapse',)
        }),
        ('Параметры сети (2G)', {
            'fields': ('bsic', 'rssi', 'rxlev', 'c1'),
            'classes': ('collapse',)
        }),
        ('Связь с устройством', {
            'fields': ('device',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('device',)


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')
    list_per_page = OPERATOR_PER_PAGE


@admin.register(DeviceOperator)
class DeviceOperatorAdmin(admin.ModelAdmin):
    list_display = (
        'operator',
        'status',
        'index',
        'last_seen',
        'operator_link',
        'device_link',
    )
    list_filter = ('status', 'operator__name')
    search_fields = ('device__mac_address',)
    autocomplete_fields = ('device', 'operator')
    list_per_page = DEVICE_OPERATOR_PER_PAGE

    def device_link(self, obj: DeviceOperator):
        if obj.device:
            return str(obj.device)
        return '-'

    device_link.short_description = 'Устройство'
    device_link.admin_order_field = 'device'

    def operator_link(self, obj: DeviceOperator):
        if obj.operator:
            return str(obj.operator)
        return '-'

    operator_link.short_description = 'Оператор'
    operator_link.admin_order_field = 'operator'

    fieldsets = (
        ('Информация об операторе', {
            'fields': ('index', 'last_seen', 'status')
        }),
        ('Связь с устройством и оператором', {
            'fields': ('device', 'operator')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('device', 'operator')
