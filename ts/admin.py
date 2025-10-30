from collections import defaultdict

from django.contrib import admin
from django.db.models import Prefetch

from core.constants import EMPTY_VALUE

from .constants import (
    AVR_CONTRACTORS_PER_PAGE,
    BASE_STATION_OPERATORS_PER_PAGE,
    BASE_STATIONS_PER_PAGE,
    CONTRACTOR_EMAILS_PER_PAGE,
    POLES_PER_PAGE,
    REGIONS_PER_PAGE,
)
from .models import (
    AVRContractor,
    BaseStation,
    BaseStationOperator,
    ContractorEmail,
    Pole,
    PoleContractorEmail,
    PoleContractorPhone,
    Region,
)

admin.site.empty_value_display = EMPTY_VALUE


class PoleEmailsInline(admin.TabularInline):
    model = PoleContractorEmail
    extra = 0
    # readonly_fields = ('contractor', 'email')
    # can_delete = False


class PolePhonesInline(admin.TabularInline):
    model = PoleContractorPhone
    extra = 0
    # readonly_fields = ('contractor', 'phone')
    # can_delete = False


@admin.register(Pole)
class PoleAdmin(admin.ModelAdmin):
    list_per_page = POLES_PER_PAGE
    list_display = (
        'pole',
        'bs_name',
        'avr_contractor',
        'infrastructure_company',
        'region',
    )
    search_fields = ('pole', 'bs_name',)
    list_filter = ('infrastructure_company', 'avr_contractor', 'region')
    inlines = [PoleEmailsInline, PolePhonesInline]
    ordering = ('pole', 'bs_name',)
    autocomplete_fields = ('region',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs
            .select_related('avr_contractor', 'region')
            .prefetch_related('avr_emails', 'avr_phones')
        )


@admin.register(AVRContractor)
class AVRContractorAdmin(admin.ModelAdmin):
    list_per_page = AVR_CONTRACTORS_PER_PAGE
    list_display = (
        'contractor_name',
        'is_excluded_from_contract',
    )
    search_fields = (
        'contractor_name',
    )
    list_filter = ('is_excluded_from_contract',)
    ordering = ('contractor_name',)
    readonly_fields = ('all_emails', 'all_phones')

    fieldsets = (
        (None, {
            'fields': ('contractor_name', 'is_excluded_from_contract')
        }),
        ('Контакты подрядчика', {
            'fields': ('all_emails', 'all_phones')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        emails_qs = PoleContractorEmail.objects.select_related('email', 'pole')
        phones_qs = PoleContractorPhone.objects.select_related('phone', 'pole')
        return qs.prefetch_related(
            Prefetch('contractor_emails', queryset=emails_qs),
            Prefetch('contractor_phones', queryset=phones_qs),
        )

    def all_emails(self, obj):
        emails = obj.contractor_emails.all().values_list(
            'email__email',
            'pole__region__region_ru',
            'pole',
        ).distinct().order_by('pole__region__region_ru', 'email__email')

        if not emails:
            return EMPTY_VALUE

        # Группируем email по региону
        region_map = defaultdict(set)
        for email, region, _ in emails:
            region_key = region if region else EMPTY_VALUE
            region_map[region_key].add(email)

        # Форматируем красиво
        formatted = []
        for region in sorted(region_map.keys()):
            email_list = sorted(region_map[region])
            formatted.append(f'{region}: {email_list}')

        return '\n'.join(formatted)

    all_emails.short_description = 'Email подрядчика'

    def all_phones(self, obj):
        phones = obj.contractor_phones.all().values_list(
            'phone__phone',
            'pole__region__region_ru',
            'pole',
        )

        if not phones:
            return EMPTY_VALUE

        formatted = [
            f'{phone} ({region})' if region else f'{phone} ({EMPTY_VALUE})'
            for phone, region, _ in phones
        ]
        return ', '.join(formatted)

    all_phones.short_description = 'Телефоны подрядчика'


@admin.register(BaseStation)
class BaseStationTSAdmin(admin.ModelAdmin):
    list_per_page = BASE_STATIONS_PER_PAGE
    list_display = ('bs_name', 'pole')
    search_fields = ('pole__pole', 'bs_name',)
    ordering = ('pole__pole',)
    filter_horizontal = ('operator',)
    autocomplete_fields = ('pole',)


@admin.register(BaseStationOperator)
class OperatorTSAdmin(admin.ModelAdmin):
    list_per_page = BASE_STATION_OPERATORS_PER_PAGE
    list_display = ('operator_name', 'operator_group',)
    search_fields = ('operator_name', 'operator_group',)
    ordering = ('operator_name',)
    list_filter = ('operator_group',)


@admin.register(ContractorEmail)
class ContractorEmailAdmin(admin.ModelAdmin):
    list_per_page = CONTRACTOR_EMAILS_PER_PAGE
    search_fields = ('email',)
    ordering = ('email',)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_per_page = REGIONS_PER_PAGE
    list_display = ('region_en', 'region_ru', 'rvr_email')
    search_fields = ('region_en', 'region_ru', 'rvr_email__email')
    ordering = ('rvr_email', 'region_en',)
    autocomplete_fields = ('rvr_email',)
    list_editable = ('rvr_email',)
