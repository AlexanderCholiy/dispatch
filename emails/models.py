import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from core.constants import MAX_EMAIL_ID_LEN
from core.models import Attachment, Detail, Msg2, SpecialEmail
from core.services.formatters import truncate_text
from core.utils import email_mime_upload_to
from incidents.models import Incident

from .constants import (
    MAX_EMAIL_LEN,
    MAX_EMAIL_STATUS_LEN,
    MAX_EMAIL_SUBJECT_LEN,
)

User = get_user_model()


class EmailStatus(models.TextChoices):
    PENDING = 'pending', 'Ожидает отправки'
    SENDING = 'sending', 'Отправляется'
    SENT = 'sent', 'Отправлено'
    FAILED = 'failed', 'Ошибка отправки'
    RETRY = 'retry', 'Повторная попытка'


class EmailErr(SpecialEmail):
    """Письма обработанные с ошибкой"""

    class Meta:
        verbose_name = 'ошибка при обработки письма'
        verbose_name_plural = 'Ошибки обработки писем'

    def __str__(self):
        return self.email_msg_id


class EmailFolder(Detail):
    """Модель для папок писем"""

    class Meta:
        verbose_name = 'папка писем'
        verbose_name_plural = 'Папки писем'
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                name='unique_email_folder'
            )
        ]

    @staticmethod
    def get_inbox():
        inbox, _ = EmailFolder.objects.get_or_create(name='INBOX')
        return inbox

    @staticmethod
    def get_inbox_id():
        return EmailFolder.get_inbox().id


class EmailMessage(models.Model):
    """Основная модель для хранения писем"""
    email_msg_id = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        unique=True,
        null=False,
        verbose_name='ID сообщения',
        db_index=True
    )
    email_msg_reply_id = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        null=True,
        blank=True,
        verbose_name='ID ответа на сообщение',
        db_index=True
    )
    email_subject = models.CharField(
        max_length=MAX_EMAIL_SUBJECT_LEN,
        null=True,
        blank=True,
        verbose_name='Тема письма',
        db_index=True
    )
    email_from = models.EmailField(
        max_length=MAX_EMAIL_LEN,
        null=False,
        verbose_name='Адрес отправителя',
        db_index=True
    )
    email_date = models.DateTimeField(
        null=False,
        verbose_name='Дата и время получения письма',
        db_index=True
    )
    email_body = models.TextField(
        null=True,
        blank=True,
        verbose_name='Тело письма'
    )
    is_first_email = models.BooleanField(
        verbose_name='Является ли первым письмом в переписке',
        db_index=True
    )
    is_email_from_yandex_tracker = models.BooleanField(
        'Было ли письмо отправлено из YandexTracker',
        db_index=True
    )
    was_added_2_yandex_tracker = models.BooleanField(
        'Было ли письмо добавлено в YandexTracker',
        db_index=True
    )
    need_2_add_in_yandex_tracker = models.BooleanField(
        'Необходимо ли перенести письмо в YandexTracker',
        default=False,
        db_index=True
    )
    status = models.CharField(
        'Статус отправки',
        max_length=MAX_EMAIL_STATUS_LEN,
        choices=EmailStatus.choices,
        default=EmailStatus.SENT,
        db_index=True,
    )
    email_incident = models.ForeignKey(
        Incident,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_messages',
        verbose_name='Номер инцидента',
        db_index=True
    )
    folder = models.ForeignKey(
        EmailFolder,
        on_delete=models.SET_DEFAULT,
        default=EmailFolder.get_inbox_id,
        related_name='email_messages',
        verbose_name='Папка письма',
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время добавления в систему',
        db_index=True,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'сообщение'
        verbose_name_plural = 'Почта'

    def __str__(self):
        safe_email_subject = truncate_text(
            self.email_subject or 'без темы', 96
        )
        return f'ID: {self.id} - {safe_email_subject}'


class EmailReference(models.Model):
    """Хранения ссылок на сообщения"""
    email_msg_references = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        null=False,
        verbose_name='Ссылка на другие сообщения',
        db_index=True
    )
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='email_references',
        verbose_name='Сообщение',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'email_msg_references'],
                name='unique_email_reference'
            )
        ]
        verbose_name = 'ссылка на email'
        verbose_name_plural = 'Ссылки на email'

    def __str__(self):
        return self.email_msg_references

    def clean(self):
        """
        Полная нормализация и валидация поля email_msg_references.

        Логика:
        1. Удаляет \r, \n, \t.
        2. Удаляет лишние пробелы и запятые.
        3. Гарантирует наличие угловых скобок < > вокруг ID.
        4. Выбрасывает ValidationError, если после очистки данных не осталось.
        """
        if not self.email_msg_references:
            raise ValidationError(
                'Поле email_msg_references не может быть пустым.'
            )

        val = str(self.email_msg_references)

        # 1. Удаление переносов строк и табуляции:
        cleaned = re.sub(r'[\r\n\t]+', '', val)

        # 2. Разделение по пробелам и запятым, фильтрация пустых:
        parts = re.split(r'[\s,]+', cleaned)
        valid_parts = [p for p in parts if p]

        # Склеиваем без разделителей (убираем пробелы внутри ID):
        normalized = ''.join(valid_parts)

        # ВАЛИДАЦИЯ 1: Если после очистки ничего не осталось
        if not normalized:
            raise ValidationError(
                'Не удалось извлечь корректный Message-ID из значения: '
                f'"{val}". '
                'Данные содержат только мусор или символы разделения.'
            )

        start_idx = normalized.find('<')
        end_idx = normalized.rfind('>')

        content = ''

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            # Скобки есть и в правильном порядке:
            content = normalized[start_idx:end_idx + 1]
        else:
            # Скобок нет или порядок нарушен -> пытаемся найти email:
            match = re.search(
                r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                normalized
            )

            if match:
                content = f'<{match.group(1)}>'
            else:
                # Если email не найден, используем остаток строки как ID:
                temp = normalized.replace('<', '').replace('>', '')
                if temp:
                    content = f'<{temp}>'
                else:
                    raise ValidationError(
                        'Не удалось восстановить корректный Message-ID '
                        f'из значения: "{val}"". '
                        'Строка не содержит ни email-адреса, ни валидного '
                        'текста.'
                    )

        # ВАЛИДАЦИЯ 2: Проверка длины и структуры
        # Content должен быть хотя бы "<x>" (минимум 3 символа)
        if len(content) <= 2:
            raise ValidationError(
                f'Сформированный Message-ID слишком короткий: "{content}". '
                'Ожидался формат <id@domain>.'
            )
        self.email_msg_references = content

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class EmailAttachment(Attachment):
    """Вложения прикрепленные к сообщению"""
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='email_attachments',
        verbose_name='Сообщение',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'file_url'],
                name='unique_email_attachment'
            )
        ]
        verbose_name = 'вложение email'
        verbose_name_plural = 'Вложения email'


class EmailInTextAttachment(Attachment):
    """Изображений вставленные в текст сообщения"""
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='email_intext_attachments',
        verbose_name='Сообщение',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'file_url'],
                name='unique_email_intext_attachment'
            )
        ]
        verbose_name = 'вложение в тексте email'
        verbose_name_plural = 'Вложения в тексте email'


class EmailTo(Msg2):
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        verbose_name='Сообщение',
        related_name='email_msg_to',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'email_to'],
                name='unique_email_to'
            )
        ]
        verbose_name = 'Получатель email'
        verbose_name_plural = 'Получатели email'


class EmailToCC(Msg2):
    email_msg = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        verbose_name='Сообщение',
        related_name='email_msg_cc',
        db_index=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'email_to'],
                name='unique_email_to_cc'
            )
        ]
        verbose_name = 'Получатель (в копии) email'
        verbose_name_plural = 'Получатели (в копии) email'


class EmailMime(Attachment):
    email_msg = models.OneToOneField(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='email_mime',
        verbose_name='Письмо',
        db_index=True,
    )
    file_url = models.FileField(
        upload_to=email_mime_upload_to,
        null=True,
        blank=True,
        verbose_name='Файл с оригиналом письма (.eml)',
        help_text='Необязательный файл с исходным письмом в формате MIME.'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email_msg', 'file_url'],
                name='unique_email_mime'
            )
        ]
        verbose_name = 'оригинальное письмо'
        verbose_name_plural = 'Оригинальные письма'

    def __str__(self):
        return f'Mime для {self.email_msg.email_msg_id}'

    @property
    def file_name(self) -> str:
        return 'original.eml'
