from django.contrib import admin

from core.constants import EMPTY_VALUE

from .constants import MAX_PLR_PER_PAGE
from .models import PlannedWork

admin.site.empty_value_display = EMPTY_VALUE


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
        'emails',
    ]

    filter_horizontal = ('emails',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('pole', 'reason', 'author')
        }),
        ('Временные рамки', {
            'fields': ('start_date', 'end_date'),
            'description': 'Дата начала по умолчанию равна текущему времени.'
        }),
        ('Связанные письма', {
            'fields': ('emails',),
            'description': (
                'Выберите письма, связанные с этой работой. '
                'Дубликаты автоматически игнорируются.'
            )
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'author',
            'pole',
        ).prefetch_related('emails',)
