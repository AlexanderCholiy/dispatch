from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from core.constants import EMPTY_VALUE
from ts.constants import UNDEFINED_CASE

from .constants import USERS_PER_PAGE
from .models import PendingUser, User, WorkSchedule

admin.site.empty_value_display = EMPTY_VALUE


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'username', 'avatar', 'role', 'date_of_birth')


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('email', 'username', 'avatar', 'role', 'date_of_birth')


class WorkScheduleInline(admin.StackedInline):
    model = WorkSchedule
    extra = 0
    can_delete = False


@admin.register(User)
class BaseUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'role',
        'is_active',
        'is_staff',
        'date_joined',
    )
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    list_editable = ('role', 'is_active')

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        (
            'Личная информация',
            {'fields': (
                'first_name',
                'last_name',
                'avatar',
                'default_avatar',
                'date_of_birth',
            )}
        ),
        (
            'Права',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'role',
                    'avr_contractor',
                    'groups',
                    'user_permissions',
                )
            }
        ),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'username',
                'avatar',
                'role',
                'password1',
                'password2',
                'is_staff',
                'is_active',
            ),
        }),
    )

    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined', 'email',)
    inlines = [WorkScheduleInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs
            .select_related('avr_contractor',)
        )

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)

        field_name = 'avr_contractor'

        if field_name in form_class.base_fields:
            field = form_class.base_fields[field_name]

            if hasattr(field, 'queryset'):

                field.queryset = field.queryset.exclude(
                    contractor_name=UNDEFINED_CASE
                )

        return form_class


@admin.register(PendingUser)
class PendingUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'last_login')
    search_fields = ('email', 'username')
    ordering = ('-last_login', 'email',)
    list_per_page = USERS_PER_PAGE
