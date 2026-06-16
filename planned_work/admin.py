from django.contrib import admin
from django.utils.html import format_html

from core.constants import EMPTY_VALUE

from .constants import MAX_PLR_CHANGE_LOG_PER_PAGE, MAX_PLR_PER_PAGE
from .models import PlannedWork, PlannedWorkChangeLog, PlannedWorkEmailLink

admin.site.empty_value_display = EMPTY_VALUE


class PlannedWorkEmailLinkInline(admin.TabularInline):
    """
    Встроенная форма для управления связями с письмами.
    Позволяет видеть дату добавления и удалять связи.
    """
    model = PlannedWorkEmailLink
    extra = 0
    show_change_link = True

    fields = ('email', 'added_at')
    readonly_fields = ('added_at',)

    autocomplete_fields = ['email']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('email').order_by('-added_at')


@admin.register(PlannedWork)
class PlannedWorkAdmin(admin.ModelAdmin):
    list_per_page = MAX_PLR_PER_PAGE

    list_editable = (
        'pole',
        'reason',
    )

    list_display = (
        'id',
        'pole',
        'reason',
        'start_date',
        'end_date',
        'author'
    )
    list_filter = (
        'reason',
        'author',
    )
    search_fields = (
        'pole__pole',
        'id',
        'reason',
    )
    date_hierarchy = 'start_date'

    ordering = ('-start_date', 'pole', 'reason')

    autocomplete_fields = [
        'pole',
        'author',
    ]

    fieldsets = (
        ('Основная информация', {
            'fields': ('pole', 'reason', 'author')
        }),
        ('Временные рамки', {
            'fields': ('start_date', 'end_date'),
            'description': 'Дата начала по умолчанию равна текущему времени.'
        }),
    )

    inlines = [
        PlannedWorkEmailLinkInline,
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'author',
            'pole',
        )


@admin.register(PlannedWorkChangeLog)
class PlannedWorkChangeLogAdmin(admin.ModelAdmin):
    list_per_page = MAX_PLR_CHANGE_LOG_PER_PAGE
    list_display = (
        'created_at',
        'planned_work_link',
        'changed_by',
        'field_name',
    )
    list_filter = (
        'created_at',
        'changed_by',
    )
    search_fields = ('planned_work__id',)
    readonly_fields = ('created_at',)
    autocomplete_fields = ('planned_work', 'changed_by')

    def planned_work_link(self, obj):
        if not obj.planned_work:
            return '-'

        url = f'/admin/planned_work/plannedwork/{obj.planned_work.pk}/change/'
        display_text = str(obj.planned_work)
        return format_html(
            '<a href="{}" target="_blank">{}</a>', url, display_text
        )

    planned_work_link.short_description = ('ПЛР')
