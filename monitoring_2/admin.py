from django.contrib import admin

from core.admin import ReadOnlyAdmin
from core.constants import EMPTY_VALUE

from .constants import (
    MODEM_LEVELS_PER_PAGE,
    MODEM_STATUSES_PER_PAGE,
    MODEMS_PER_PAGE,
    POLE_STATUSES_PER_PAGE,
)
from .models import (
    Counter,
    Modem,
    ModemLevel,
    ModemNotification,
    ModemPoleRealtion,
    ModemStatus,
    PoleStatus,
)

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(ModemStatus)
class ModemStatusAdmin(ReadOnlyAdmin):
    list_per_page = MODEM_STATUSES_PER_PAGE
    list_display = (
        'id',
        'level',
        'level_description',
    )
    search_fields = ('id', 'level', 'level_description',)
    ordering = ('level', 'id',)


@admin.register(PoleStatus)
class PoleStatusAdmin(ReadOnlyAdmin):
    list_per_page = POLE_STATUSES_PER_PAGE
    list_display = (
        'id',
        'level',
        'level_description',
    )
    search_fields = ('id', 'level', 'level_description',)
    ordering = ('level', 'id',)


@admin.register(ModemLevel)
class ModemLevelAdmin(ReadOnlyAdmin):
    list_per_page = MODEM_LEVELS_PER_PAGE
    list_display = (
        'id',
        'description',
    )
    search_fields = ('id', 'description',)
    ordering = ('description', 'id',)


class ModemPoleRealtionInline(admin.TabularInline):
    model = ModemPoleRealtion
    extra = 0
    can_delete = False
    show_change_link = False
    fields = (
        'pole',
        'dismantled',
        'dismantled_at',
    )
    readonly_fields = (
        'pole',
        'dismantled',
        'dismantled_at',
    )


class ModemNotificationInline(admin.TabularInline):
    model = ModemNotification
    extra = 0
    can_delete = False
    show_change_link = False
    fields = (
        'action',
        'sent_at',
    )
    readonly_fields = (
        'action',
        'sent_at',
    )
    verbose_name = 'Уведомление'
    verbose_name_plural = 'Уведомления'


class CounterInline(admin.TabularInline):
    model = Counter
    extra = 0
    can_delete = False
    fields = ('counter_number',)
    show_change_link = False


@admin.register(Modem)
class ModemAdmin(ReadOnlyAdmin):
    list_per_page = MODEMS_PER_PAGE
    list_display = (
        'ip',
        'level',
        'status',
        'mac',
        'serial',
        'last_data_at',
    )
    search_fields = (
        'ip',
        'mac',
        'serial',
        'cabinet',
    )
    list_filter = (
        'level',
        'status',
        'slate',
    )
    readonly_fields = (
        'id',
        'ip',
        'level',
        'status',
        'slate',
        'created_at',
        'last_data_at',
        'mac',
        'serial',
        'version',
        'firmware',
        'cabinet',
        'coordinates',
    )
    fieldsets = (
        (None, {
            'fields': (
                'status',
                'slate',
            ),
        }),
        ('Щит', {
            'fields': (
                'level',
                'cabinet',
            ),
        }),
        ('Контроллер', {
            'fields': (
                'serial',
                'mac',
                'version',
                'firmware',
            ),
            'classes': ('collapse',),
        }),
        ('Мета', {
            'fields': (
                'created_at',
                'last_data_at',
                'coordinates',
            ),
            'classes': ('collapse',),
        }),
    )
    inlines = (
        ModemPoleRealtionInline,
        ModemNotificationInline,
        CounterInline,
    )
    ordering = ('-id',)
