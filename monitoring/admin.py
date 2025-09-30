from django.contrib import admin

from core.constants import EMPTY_VALUE

from .constants import (
    MSYS_MODEMS_PER_PAGE,
    MSYS_POLES_PER_PAGE,
    MSYS_STATUSES_PER_PAGE,
)
from .models import MSysModem, MSysPoles, MSysStatus

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(MSysModem)
class MSysModemAdmin(admin.ModelAdmin):
    list_per_page = MSYS_MODEMS_PER_PAGE
    list_display = (
        'modem_ip',
        'level',
        'status',
        'pole_1',
        'updated_at',
    )
    search_fields = (
        'modem_ip', 'pole_1__pole', 'pole_2__pole', 'pole_3__pole'
    )
    autocomplete_fields = ('pole_1', 'pole_2', 'pole_3', 'status',)
    ordering = ('updated_at', 'modem_ip',)


@admin.register(MSysPoles)
class MSysPolesAdmin(admin.ModelAdmin):
    list_per_page = MSYS_POLES_PER_PAGE
    list_display = (
        'pole',
        'status',
    )
    search_fields = ('pole',)
    autocomplete_fields = ('status',)


@admin.register(MSysStatus)
class MSysStatusAdmin(admin.ModelAdmin):
    list_per_page = MSYS_STATUSES_PER_PAGE
    list_display = (
        'id',
        'description',
    )
    search_fields = ('id', 'description',)
    ordering = ('id',)
