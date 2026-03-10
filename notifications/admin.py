from django.contrib import admin

from core.constants import EMPTY_VALUE

from .constants import NOTIFICATIONS_PER_PAGE
from .models import Notification

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_per_page = NOTIFICATIONS_PER_PAGE
    list_display = (
        'user',
        'title',
        'read',
        'level',
        'send_at',
        'is_overdue',
    )

    list_filter = ('level', 'read', 'user')
    list_editable = ('level', 'read')

    search_fields = ('title', 'message', 'user__username', 'user__email')

    readonly_fields = ('created_at', 'is_overdue')

    autocomplete_fields = ['user']

    fieldsets = (
        (None, {
            'fields': (
                'user',
                'title',
                'message',
                'level',
                'data',
                'read',
                'send_at',
            )
        }),
        ('Дополнительно', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def is_overdue(self, obj: Notification):
        return obj.is_overdue()
    is_overdue.boolean = True
    is_overdue.short_description = 'Просрочено'
    is_overdue.admin_order_field = 'send_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user',)
