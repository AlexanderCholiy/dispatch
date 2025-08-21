import os

from django.db import models

from emails.constants import MAX_EMAIL_LEN

from .constants import (
    MAX_EMAIL_ID_LEN,
    MAX_FILE_NAME_LEN,
    MAX_FILE_URL_LEN,
    MAX_LG_DESCRIPTION,
    MAX_ST_DESCRIPTION,
    INCIDENT_DIR,
)


class Attachment(models.Model):
    """
    Абстрактная модель для вложений из почты. Файл необходимо сначала скачать.
    """
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

    def build_file_url(self) -> str | None:
        """
        Формирует URL до файла (без сохранения).
        Ожидается, что ФАЙЛ УЖЕ СКАЧАН в
        INCIDENT_DIR/<subfolder>/<file_name>.
        """
        absolute_path = os.path.join(INCIDENT_DIR, self.file_url)

        if os.path.exists(absolute_path):
            rel_url = self.file_url.replace(os.sep, '/')
            return rel_url
        return None

    def save(self, *args, **kwargs):
        """Проверяем ссылку при сохранении модели и формируем имя файла."""
        if os.path.sep in self.file_name:
            self.file_name = os.path.basename(self.file_name)

        file_url = self.build_file_url()

        if file_url:
            self.file_url = file_url
            super().save(*args, **kwargs)
        else:
            if self.pk:
                super().delete()

    def delete(self, *args, **kwargs):
        """Удаляем не только запись, но и сам файл."""
        absolute_path = os.path.join(INCIDENT_DIR, self.file_url)

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
