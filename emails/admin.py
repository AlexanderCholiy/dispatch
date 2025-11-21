from django.contrib import admin
from django.utils.html import format_html

from core.constants import EMPTY_VALUE

from .constants import EMAILS_PER_PAGE
from .models import (
    EmailAttachment,
    EmailErr,
    EmailFolder,
    EmailInTextAttachment,
    EmailMessage,
    EmailMime,
)

admin.site.empty_value_display = EMPTY_VALUE


@admin.register(EmailErr)
class EmailErrAdmin(admin.ModelAdmin):
    list_display = ('email_msg_id', 'incert_date',)


@admin.register(EmailFolder)
class EmailFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'description',)


class EmailMimeInline(admin.StackedInline):
    model = EmailMime
    extra = 0
    can_delete = False
    fields = ('protected_file_link', 'created_at')

    readonly_fields = ('protected_file_link', 'created_at')

    def protected_file_link(self, obj: EmailMime):
        """Ссылка на скачивание .eml файла"""
        protected_url = obj.protected_url
        if protected_url:
            return format_html(
                f'<a href="{protected_url}" target="_blank">'
                'Скачать MIME (.eml)'
                '</a>',
            )
        return format_html('<span>–</span>')

    protected_file_link.short_description = 'Файл MIME (.eml)'


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_per_page = EMAILS_PER_PAGE
    list_display = (
        'id',
        'email_incident',
        'email_subject',
        'email_from',
        'email_date',
    )
    search_fields = (
        'id',
        'email_incident__id',
        'email_subject',
        'email_msg_id',
    )
    list_editable = ('email_incident',)
    ordering = ('-email_date',)
    autocomplete_fields = ('email_incident',)
    list_filter = (
        'is_first_email',
        'is_email_from_yandex_tracker',
        'was_added_2_yandex_tracker',
        'folder',
    )
    inlines = [EmailMimeInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('email_incident', 'folder', 'email_mime')

    readonly_fields = (
        'email_attachments_list',
        'email_intext_attachments_list',
        'get_email_recipients_to',
        'get_email_recipients_cc',
    )

    fieldsets = (
        ('Мета', {
            'classes': ('collapse',),
            'fields': (
                'email_msg_id',
                'is_first_email',
                'is_email_from_yandex_tracker',
                'was_added_2_yandex_tracker',
                'need_2_add_in_yandex_tracker',
                'folder',
            )
        }),
        (None, {
            'fields': (
                'email_incident',
                'email_subject',
                'email_from',
                'get_email_recipients_to',
                'get_email_recipients_cc',
                'email_date',
                'email_body',
            )
        }),
        ('Прикрепленные файлы', {
            'classes': ('collapse',),
            'fields': (
                'email_attachments_list',
                'email_intext_attachments_list',
            )
        }),
    )

    def _render_attachment_list(
        self, attachments: EmailAttachment | EmailInTextAttachment
    ):
        """Общая функция для генерации списка вложений"""
        file_links = [
            att.get_admin_attachment_url
            for att in attachments
            if att.get_admin_attachment_url
        ]
        if file_links:
            file_links.sort()
            return format_html('<br>'.join(file_links))
        return '–'

    def email_attachments_list(self, obj: EmailMessage):
        return self._render_attachment_list(obj.email_attachments.all())

    email_attachments_list.short_description = 'Вложения'

    def email_intext_attachments_list(self, obj: EmailMessage):
        return self._render_attachment_list(obj.email_intext_attachments.all())

    email_intext_attachments_list.short_description = 'Вложения в тексте'

    def get_email_recipients_to(self, obj: EmailMessage):
        """Метод для отображения получателей письма"""
        recipients = obj.email_msg_to.all()
        if recipients:
            email_to = [recipient.email_to for recipient in recipients]
            return format_html('<br>'.join(email_to))
        return '–'

    get_email_recipients_to.short_description = 'Кому'

    def get_email_recipients_cc(self, obj: EmailMessage):
        """Метод для отображения получателей письма"""
        recipients = obj.email_msg_cc.all()
        if recipients:
            email_to = [recipient.email_to for recipient in recipients]
            return format_html('<br>'.join(email_to))
        return '–'

    get_email_recipients_cc.short_description = 'Копия'
