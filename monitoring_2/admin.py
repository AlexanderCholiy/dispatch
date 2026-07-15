from django.contrib import admin

from core.admin import ReadOnlyAdmin
from core.constants import EMPTY_VALUE

from .constants import (
    MODEM_STATUSES_PER_PAGE,
)
from .models import ModemStatus

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(ModemStatus)
class MSysStatusAdmin(ReadOnlyAdmin):
    list_per_page = MODEM_STATUSES_PER_PAGE
    list_display = (
        'id',
        'level',
        'level_description',
    )
    search_fields = ('id', 'level', 'level_description',)
    ordering = ('level', 'id',)
