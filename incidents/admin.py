import pytz
from datetime import timedelta, datetime
from typing import Optional

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.conf import settings

from emails.models import EmailMessage
from .models import IncidentStatusHistory, Incident
from .constants import INCIDENTS_PER_PAGE
from core.constants import EMPTY_VALUE

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
        return qs.order_by('email_date', 'id')

    def view_link(self, obj):
        url = reverse('admin:incidents_emailmessage_change', args=[obj.id])
        return format_html('<a href="{}">Перейти к письму</a>', url)

    view_link.short_description = 'Ссылка на письмо'


class IncidentStatusHistoryInline(admin.TabularInline):
    model = IncidentStatusHistory
    extra = 1
    verbose_name = 'Статус инцидента'
    verbose_name_plural = 'Статусы инцидента'


class LatestStatusFilter(admin.SimpleListFilter):
    title = 'Статус'
    parameter_name = 'latest_status'

    def lookups(self, request, model_admin):
        statuses = (
            IncidentStatusHistory
            .objects.values_list('status__name', flat=True).distinct()
        )
        return [(status, status) for status in statuses]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                status_history__status__name=self.value()
            ).distinct()
        return queryset


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_per_page = INCIDENTS_PER_PAGE
    list_display = (
        'id',
        'incident_date',
        'pole',
        'incident_type',
        'responsible_user',
        'get_sla_deadline',
        'is_sla_expired',
        'track_sla',
    )
    search_fields = ('pole__pole', 'id',)
    list_filter = (
        LatestStatusFilter,
        'incident_type',
        'responsible_user',
        'track_sla',
    )
    autocomplete_fields = ('pole', 'base_station')
    list_editable = ('incident_type', 'responsible_user')

    inlines = [IncidentStatusHistoryInline, EmailMessageInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'responsible_user',
            'incident_type',
            'pole',
            'base_station',
        ).prefetch_related(
            'responsible_user__incidents',
            'incident_type__incidents',
            'pole__incidents',
            'avr_contractor__incidents',
            'base_station__incidents',
        )

    def get_sla_deadline(self, obj: Incident) -> Optional[datetime]:
        """
        Возвращает срок устранения аварии из типа инцидента в локальной
        временной зоне.
        """
        if obj.incident_type and obj.incident_type.sla_deadline:
            sla_deadline = obj.incident_date - timedelta(
                minutes=obj.incident_type.sla_deadline)

            local_tz = pytz.timezone(settings.TIME_ZONE)
            return sla_deadline.astimezone(local_tz)
        return EMPTY_VALUE
    get_sla_deadline.short_description = 'Срок устранения'

    readonly_fields = ('get_sla_deadline', 'is_sla_expired')

    fieldsets = (
        (None, {
            'fields': (
                'incident_date',
                'pole',
                'base_station',
                'incident_type',
                'responsible_user',
                'avr_contractor',
                'get_sla_deadline',
                'is_sla_expired',
            ),
        }),
    )

    def is_sla_expired(self, obj: Incident) -> Optional[bool]:
        return obj.is_sla_expired or EMPTY_VALUE
    is_sla_expired.short_description = 'SLA истек'
