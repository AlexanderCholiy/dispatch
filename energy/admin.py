from django.contrib import admin

from .constants import REQUESTS_PER_PAGE
from .models import (
    Appeal,
    AppealAttr,
    AppealStatus,
    AttrType,
    Claim,
    ClaimAttr,
    ClaimStatus,
    Company,
    Declarant,
)


@admin.register(Declarant)
class DeclarantAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name', 'id',)
    readonly_fields = ('id',)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name', 'id',)
    readonly_fields = ('id',)


@admin.register(AttrType)
class AttrTypeAdmin(admin.ModelAdmin):
    list_display = ('attribute_id', 'name', 'description')
    search_fields = ('name', 'description')
    ordering = ('attribute_id', 'id',)
    readonly_fields = (
        'id',
        'attribute_id',
    )


class EnergyStatusInline(admin.TabularInline):
    extra = 0
    can_delete = False
    show_change_link = False
    readonly_fields = ('created_at',)
    fields = ('name', 'date', 'created_at')
    ordering = ('-date', '-created_at')


class ClaimStatusInline(EnergyStatusInline):
    model = ClaimStatus

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('claim')


class AppealStatusInline(EnergyStatusInline):
    model = AppealStatus

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('appeal')


class EnergyAttrInline(admin.TabularInline):
    extra = 0
    can_delete = False
    show_change_link = False
    readonly_fields = ('created_at',)
    fields = ('attr_type', 'text')
    ordering = ('attr_type',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('attr_type')


class ClaimAttrInline(EnergyAttrInline):
    model = ClaimAttr


class AppealAttrInline(EnergyAttrInline):
    model = AppealAttr


class EnergyRequestAdmin(admin.ModelAdmin):
    list_display = ('number', 'company', 'declarant')
    search_fields = ('number',)
    ordering = ('id',)
    list_filter = ('company', 'declarant')
    readonly_fields = ('id',)
    list_per_page = REQUESTS_PER_PAGE

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('company', 'declarant')
        return qs


@admin.register(Claim)
class ClaimsAdmin(EnergyRequestAdmin):
    inlines = (
        ClaimAttrInline,
        ClaimStatusInline,
    )


@admin.register(Appeal)
class AppealAdmin(EnergyRequestAdmin):
    inlines = (
        AppealAttrInline,
        AppealStatusInline,
    )
