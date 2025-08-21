from datetime import timedelta, datetime
from typing import Optional

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.conf import settings
import pytz

from .constants import (
    POLES_PER_PAGE,
    AVR_CONTRACTORS_PER_PAGE,
    BASE_STATIONS_PER_PAGE,
    BASE_STATION_OPERATORS_PER_PAGE,
)
from .models import (
    Pole, AVRContractor, BaseStation, BaseStationOperator,
)
from core.constants import EMPTY_VALUE

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(Pole)
class PoleAdmin(admin.ModelAdmin):
    list_per_page = POLES_PER_PAGE
    list_display = (
        'pole',
        'bs_name',
        'address',
        'infrastructure_company',
        'region',
    )
    search_fields = ('pole', 'bs_name', 'address',)
    list_filter = ('infrastructure_company', 'region')


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
    filter_horizontal = ('emails', 'phones',)


@admin.register(BaseStation)
class BaseStationTSAdmin(admin.ModelAdmin):
    list_per_page = BASE_STATIONS_PER_PAGE
    list_display = ('pole', 'bs_name',)
    search_fields = ('pole__pole', 'bs_name',)
    list_filter = ('operator',)
    ordering = ('pole__pole',)
    filter_horizontal = ('operator',)
    autocomplete_fields = ['pole']


@admin.register(BaseStationOperator)
class OperatorTSAdmin(admin.ModelAdmin):
    list_per_page = BASE_STATION_OPERATORS_PER_PAGE
    list_display = ('operator_name', 'operator_group',)
    search_fields = ('operator_name', 'operator_group',)
    ordering = ('operator_name',)
    list_filter = ('operator_group',)
