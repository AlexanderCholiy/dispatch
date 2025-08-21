import os
from pathlib import Path

from django.conf import settings
from django.db import models

from emails.constants import MAX_EMAIL_LEN

from .constants import (
    EMAIL_ATTACHMENT_FOLDER_NAME,
    MAX_EMAIL_ID_LEN,
    MAX_FILE_NAME_LEN,
    MAX_FILE_URL_LEN,
    MAX_LG_DESCRIPTION,
    MAX_ST_DESCRIPTION,
    SUBFOLDER_DATE_FORMAT,
)


class Attachment(models.Model):
    """Абстрактная модель для вложений из почты"""
    file_name = models.CharField(
        max_length=MAX_FILE_NAME_LEN,
        verbose_name='Имя файла'
    )
    file_url = models.URLField(
        max_length=MAX_FILE_URL_LEN,
        blank=True,
        null=True,
        verbose_name='Ссылка на файл'
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.file_name

    @property
    def subfolder_name(self):
        return self.email_msg.email_date.strftime(SUBFOLDER_DATE_FORMAT)

    def build_file_url(self) -> str | None:
        """Формирует URL до файла (без сохранения)."""
        relative_path = (
            Path(EMAIL_ATTACHMENT_FOLDER_NAME)
            / self.subfolder_name / self.file_name
        )
        absolute_path = Path(settings.MEDIA_ROOT) / relative_path

        if absolute_path.exists():
            return f"{settings.MEDIA_URL}{relative_path.as_posix()}"
        return None

    def save(self, *args, **kwargs):
        """Автоматически сохраняем ссылку при сохранении модели."""
        file_url = self.build_file_url()
        if file_url:
            self.file_url = file_url
            super().save(*args, **kwargs)
        else:
            if self.pk:
                super().delete()

    def delete(self, *args, **kwargs):
        """Удаляем не только запись, но и сам файл."""
        relative_path = os.path.join(
            EMAIL_ATTACHMENT_FOLDER_NAME, self.subfolder_name, self.file_name
        )
        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        if os.path.exists(absolute_path):
            try:
                os.remove(absolute_path)
            except OSError:
                pass

        super().delete(*args, **kwargs)


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
    """Модель для хранения получателей сообщения"""
    email_to = models.EmailField(
        max_length=MAX_EMAIL_LEN,
        null=False,
        verbose_name='Адрес получателя'
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.email_to
