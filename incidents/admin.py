from django.contrib import admin
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html

from core.constants import EMPTY_VALUE
from emails.models import EmailMessage

from .constants import (
    INCIDENT_CATEGORIES_PER_PAGE,
    INCIDENT_STATUSES_PER_PAGE,
    INCIDENT_TYPES_PER_PAGE,
    INCIDENTS_PER_PAGE,
)
from .models import (
    Incident,
    IncidentCategory,
    IncidentCategoryRelation,
    IncidentStatus,
    IncidentStatusHistory,
    IncidentType,
)

admin.site.empty_value_display = EMPTY_VALUE


class EmailMessageInline(admin.StackedInline):
    model = EmailMessage
    extra = 0
    fields = (
        'view_link',
        'email_from',
        'email_date',
        'email_subject',
        'email_body',
    )
    readonly_fields = ('view_link',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('email_date', '-is_first_email', 'id')

    def view_link(self, obj):
        url = reverse('admin:emails_emailmessage_change', args=[obj.id])
        return format_html('<a href="{}">Перейти к письму</a>', url)

    view_link.short_description = 'Ссылка на письмо'


class IncidentStatusHistoryInline(admin.TabularInline):
    model = IncidentStatusHistory
    extra = 1
    autocomplete_fields = ['status']
    verbose_name = 'Статус инцидента'
    verbose_name_plural = 'Статусы инцидента'


class IncidentCategoryRelationInline(admin.TabularInline):
    model = IncidentCategoryRelation
    extra = 0
    autocomplete_fields = ['category']
    verbose_name = 'Категория инцидента'
    verbose_name_plural = 'Категории инцидента'


class IncidentCategoryFilter(admin.SimpleListFilter):
    title = 'Категория инцидента'
    parameter_name = 'category'

    def lookups(self, request: HttpRequest, model_admin):
        return [
            (c.id, c.name)
            for c in IncidentCategory.objects.all().order_by('name')
        ]

    def queryset(self, request: HttpRequest, queryset):
        if self.value():
            return queryset.filter(categories__id=self.value())
        return queryset


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_per_page = INCIDENTS_PER_PAGE
    list_display = (
        'id',
        'code',
        'pole',
        'responsible_user',
        'incident_type',
        'get_last_status',
        'incident_date',
    )
    search_fields = ('pole__pole', 'id', 'code')
    list_filter = (
        'incident_type',
        'responsible_user',
        'is_incident_finish',
        IncidentCategoryFilter,
    )
    autocomplete_fields = ('pole', 'base_station')
    list_editable = ('incident_type', 'responsible_user')

    inlines = [
        IncidentCategoryRelationInline,
        IncidentStatusHistoryInline,
        EmailMessageInline,
    ]

    def get_last_status(self, obj):
        latest = obj.status_history.order_by('-insert_date').first()
        return latest.status.name if latest else EMPTY_VALUE
    get_last_status.short_description = 'Статус'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'pole',
            'base_station',
            'responsible_user',
            'incident_type',
        ).prefetch_related('statuses', 'categories')

    readonly_fields = ('avr_contractor', 'sla_deadline', 'is_sla_expired')

    fieldsets = (
        (None, {
            'fields': (
                'incident_date',
                'pole',
                'base_station',
                'incident_type',
                'responsible_user',
                'avr_contractor',
                'sla_deadline',
                'is_sla_expired',
            ),
        }),
        ('Мета', {
            'classes': ('collapse',),
            'fields': (
                'is_incident_finish',
                'is_auto_incident',
                'code',
                'avr_start_date',
                'avr_end_date',
                'rvr_start_date',
                'rvr_end_date',
            ),
        }),
    )


@admin.register(IncidentType)
class IncidentTypeAdmin(admin.ModelAdmin):
    list_per_page = INCIDENT_TYPES_PER_PAGE
    list_display = ('name', 'sla_deadline')
    list_editable = ('sla_deadline',)
    search_fields = ('name',)


@admin.register(IncidentStatus)
class IncidentStatusAdmin(admin.ModelAdmin):
    list_per_page = INCIDENT_STATUSES_PER_PAGE
    list_display = ('name', 'description',)
    list_editable = ('description',)
    search_fields = ('name', 'description',)
    ordering = ('name',)


@admin.register(IncidentCategory)
class IncidentCategoryAdmin(admin.ModelAdmin):
    list_per_page = INCIDENT_CATEGORIES_PER_PAGE
    list_display = ('name', 'description',)
    list_editable = ('description',)
    search_fields = ('name', 'description',)
    ordering = ('name',)
