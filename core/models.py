import os

from django.db import models

from emails.constants import MAX_EMAIL_LEN

from .constants import (
    MAX_EMAIL_ID_LEN,
    MAX_FILE_URL_LEN,
    MAX_LG_DESCRIPTION,
    MAX_ST_DESCRIPTION,
)
from .utils import attachment_upload_to


class Attachment(models.Model):
    """Абстрактная модель для вложений. Файл хранится в папке MEDIA_ROOT."""

    file_url = models.FileField(
        upload_to=attachment_upload_to,
        max_length=MAX_FILE_URL_LEN,
        verbose_name='Ссылка на файл',
    )

    class Meta:
        abstract = True

    def __str__(self):
        if (
            self.file_url
            and hasattr(self.file_url, 'name')
            and self.file_url.name
        ):
            return os.path.basename(self.file_url.name)
        return 'Нет файла'

    def delete(self, *args, **kwargs):
        if self.file_url and self.file_url.name:
            file_path = self.file_url.path
            if os.path.isfile(file_path):
                os.remove(file_path)
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.pk:
            old = self.objects.filter(pk=self.pk).first()
            if (
                old
                and old.file_url
                and old.file_url.name != self.file_url.name
            ):
                old_path = old.file_url.path
                if os.path.isfile(old_path):
                    os.remove(old_path)
        super().save(*args, **kwargs)

    @property
    def get_attachment_url(self):
        """Данный метод нужен для удобства в админ панели."""
        if self.file_url and hasattr(self.file_url, 'url'):
            return (
                f'<a href="{self.file_url.url}" target="_blank">'
                f'{os.path.basename(self.file_url.name)}</a>'
            )
        return None

    @property
    def file_name(self) -> str:
        """Возвращает только имя файла без пути."""
        if (
            self.file_url
            and hasattr(self.file_url, 'name')
            and self.file_url.name
        ):
            base = os.path.basename(self.file_url.name)
            parts = base.split('__')
            return parts[-1] if parts else base
        return 'unknown'


class Detail(models.Model):
    """Подробное описание к основной модели"""
    name = models.CharField(
        max_length=MAX_ST_DESCRIPTION,
        unique=True,
        null=False,
        verbose_name='Название'
    )
    description = models.CharField(
        max_length=MAX_LG_DESCRIPTION,
        null=True,
        blank=True,
        verbose_name='Описание'
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class SpecialEmail(models.Model):
    """Модель для email которые необходимо пометить"""
    email_msg_id = models.CharField(
        max_length=MAX_EMAIL_ID_LEN,
        unique=True,
        null=False,
        verbose_name='ID сообщения',
    )
    incert_date = models.DateTimeField(
        auto_now_add=True,
        null=False,
        verbose_name='Дата и время добавления',
    )

    class Meta:
        abstract = True


class Msg2(models.Model):
    """Модель для хранения получателей сообщения."""
    email_to = models.EmailField(
        max_length=MAX_EMAIL_LEN,
        null=False,
        verbose_name='Адрес получателя'
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.email_to
