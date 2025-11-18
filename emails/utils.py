import html
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.files import File
from django.db import DatabaseError, models, transaction
from django.utils import timezone

from core.constants import (
    INCIDENTS_LOG_ROTATING_FILE,
    SUBFOLDER_DATE_FORMAT,
    SUBFOLDER_EMAIL_NAME
)
from core.loggers import LoggerFactory
from core.models import Attachment
from incidents.models import Incident

from .models import (
    EmailAttachment,
    EmailErr,
    EmailFolder,
    EmailInTextAttachment,
    EmailMessage,
    EmailReference,
    EmailTo,
    EmailToCC,
    EmailMime,
)

incident_manager_logger = LoggerFactory(
    __name__, INCIDENTS_LOG_ROTATING_FILE
).get_logger()


class EmailManager:

    @staticmethod
    def is_nth_email_after_incident_close(
        incident: Incident, n: int
    ) -> bool:
        """Пришло ли n-ое письмо после закрытия инцидента."""
        if (
            not incident.is_incident_finish
            or not incident.incident_finish_date
        ):
            return False

        emails_after_close = incident.email_messages.filter(
            email_date__gt=incident.incident_finish_date,
            folder=EmailFolder.get_inbox()
        ).order_by('email_date')

        try:
            emails_after_close[n - 1]
            return True
        except IndexError:
            return False

    @staticmethod
    @transaction.atomic
    def add_err_msg_bulk(error_ids: list[str]):
        if not error_ids:
            return

        objs_to_create = [
            EmailErr(email_msg_id=msg_id) for msg_id in error_ids
        ]

        EmailErr.objects.bulk_create(objs_to_create, ignore_conflicts=True)

    @staticmethod
    @transaction.atomic
    def del_err_msg_bulk(error_ids: list[str]):
        if not error_ids:
            return

        EmailErr.objects.filter(email_msg_id__in=error_ids).delete()

    @transaction.atomic
    def add_email_message(
        self,
        email_msg_id: str,
        email_msg_reply_id: Optional[str],
        email_subject: Optional[str],
        email_from: str,
        email_date: datetime,
        email_body: Optional[str],
        is_first_email: bool,
        is_email_from_yandex_tracker: bool,
        was_added_2_yandex_tracker: bool,
        email_to: list[str],
        email_to_cc: list[str],
        email_msg_references: list[str],
        email_attachments_urls: list[str],
        email_attachments_intext_urls: list[str],
        folder: EmailFolder,
    ) -> EmailMessage:
        """Добавление (обновление) сообщения электронной почты в БД."""
        email_message, _ = EmailMessage.objects.update_or_create(
            email_msg_id=email_msg_id,
            defaults={
                'email_msg_reply_id': email_msg_reply_id,
                'email_subject': email_subject,
                'email_from': email_from,
                'email_date': email_date,
                'email_body': email_body,
                'is_first_email': is_first_email,
                'is_email_from_yandex_tracker': (
                    is_email_from_yandex_tracker
                ),
                'was_added_2_yandex_tracker': (
                    was_added_2_yandex_tracker
                ),
                'folder': folder,
            },
        )

        self._update_related_records(
            EmailReference, 'email_msg_references',
            email_message, email_msg_references
        )
        self._update_related_records(
            EmailAttachment, 'file_url',
            email_message, email_attachments_urls
        )
        self._update_related_records(
            EmailInTextAttachment, 'file_url',
            email_message, email_attachments_intext_urls
        )
        self._update_related_records(
            EmailTo, 'email_to',
            email_message, email_to
        )
        self._update_related_records(
            EmailToCC, 'email_to',
            email_message, email_to_cc
        )

        return email_message

    def _update_related_records(
        self,
        model: models.Model,
        field_name: str,
        email_message: EmailMessage,
        values: list[str]
    ):
        if not values:
            return

        existing_values = set(
            model.objects.filter(email_msg=email_message)
            .values_list(field_name, flat=True)
        )
        new_values = set(values) - existing_values

        objs = []

        for value in new_values:
            if issubclass(model, Attachment):
                # Формируем относительный путь для сохранения в БД:
                date_str = (
                    email_message.email_date.strftime(SUBFOLDER_DATE_FORMAT)
                    if email_message.email_date else timezone.now().strftime(
                        SUBFOLDER_DATE_FORMAT
                    )
                )
                relative_path = os.path.join(
                    SUBFOLDER_EMAIL_NAME, date_str, os.path.basename(value)
                ).replace(os.sep, '/')

                obj = model(email_msg=email_message)

                if os.path.isfile(value):
                    # Если есть физический файл, сохраняем его через FileField:
                    with open(value, 'rb') as f:
                        obj.file_url.save(
                            os.path.basename(value), File(f), save=False)
                        obj.file_url.name = relative_path
                else:
                    obj.file_url.name = relative_path

                objs.append(obj)
            else:
                obj = model(email_msg=email_message, **{field_name: value})
                objs.append(obj)

        model.objects.bulk_create(objs, ignore_conflicts=True)

    @staticmethod
    def delete_attachment_safely(
        attachment: EmailAttachment | EmailInTextAttachment, reason: str
    ):
        try:
            attachment.delete()

        except DatabaseError as e:
            incident_manager_logger.warning(
                f'Ошибка базы данных при удалении {type(attachment)} '
                f'{attachment.pk} ({reason}): {e}'
            )

        except KeyboardInterrupt:
            raise

        except Exception:

            incident_manager_logger.exception(
                f'Ошибка удаления {type(attachment)} {attachment.pk} '
                f'({reason})'
            )

    @staticmethod
    def valid_email_file_path(
        attachments: (
            list[EmailAttachment]
            | list[EmailInTextAttachment]
            | list[EmailMime]
        )
    ) -> list[str]:
        """
        Возвращает список валидных путей к вложениям.
        Удаляет записи из БД, если файл отсутствует или некорректен.
        """
        valid_files = []

        for attachment in attachments:
            relative_file_path = Path(attachment.file_url.name)
            file_path = os.path.join(
                settings.MEDIA_ROOT, str(relative_file_path)
            )

            if not file_path or not os.path.isfile(file_path):
                EmailManager.delete_attachment_safely(
                    attachment, reason='файл отсутствует или путь некорректен'
                )
                continue

            try:
                size = os.path.getsize(file_path)
            except OSError as e:
                incident_manager_logger.warning(
                    f'Ошибка при получении размера файла "{file_path}": {e}'
                )
                continue

            if size == 0:
                EmailManager.delete_attachment_safely(
                    attachment, reason='размер файла равен 0'
                )
                continue

            valid_files.append(file_path)

        return valid_files

    @staticmethod
    def get_email_attachments(email: EmailMessage) -> list[str]:
        """
        Возвращает список реальных путей к файлам, если они существуют.

        Записи, для которых файл отсутсвует удаляются.
        """
        email_attachments = EmailAttachment.objects.filter(
            email_msg=email
        ).order_by('file_url')
        email_intext_attachments = EmailInTextAttachment.objects.filter(
            email_msg=email
        ).order_by('file_url')

        return list(
            EmailManager.valid_email_file_path(email_attachments)
            + EmailManager.valid_email_file_path(email_intext_attachments)
        )

    @staticmethod
    def get_email_mimes(email: EmailMessage) -> list[str]:
        """
        Возвращает список реальных путей к файлам, если они существуют.

        Записи, для которых файл отсутсвует удаляются.
        """
        email_mime = EmailMime.objects.filter(
            email_msg=email
        ).order_by('file_url')

        return list(
            EmailManager.valid_email_file_path(email_mime)
        )

    @staticmethod
    def normalize_text_with_json(
        text: str, clean_for_code_block: bool = False
    ) -> str:
        """
        Универсальная функция для обработки текста:
        - Ищет и красиво форматирует JSON
        - Очищает HTML и нормализует текст
        - Опционально подготавливает для code block

        :param text: Исходный текст для обработки
        :param clean_for_code_block: Если True, подготавливает для отображения
        в code block
        :return: Обработанный текст
        """

        # 1. Первичная очистка HTML
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<p>', '\n\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<div>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</div>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<.*?>', '', text)  # Удаляем все остальные HTML теги

        # 2. Обрабатываем HTML entities
        text = html.unescape(text)

        # 3. Ищем и форматируем JSON (только если не готовим для code block)
        if not clean_for_code_block:
            json_pattern = re.compile(
                (
                    r'(\{(?:[^{}]|(?:\{(?:[^{}]|)*\}))*\}|\[(?:[^\[\]]|(?:'
                    r'\[(?:[^\[\]]|)*\]))*\])'
                ),
                re.DOTALL
            )

            def dict_to_pretty(data, indent: int = 0) -> str:
                """Рекурсивно преобразует dict/list в читаемый текст"""
                spaces = '  ' * indent
                if isinstance(data, dict):
                    items = []
                    for key, value in data.items():
                        text = dict_to_pretty(value, indent + 1)
                        items.append(
                            f'{spaces}{key}: {text}'
                        )
                    return '\n'.join(items)
                elif isinstance(data, list):
                    items = []
                    for item in data:
                        text = dict_to_pretty(item, indent + 1)
                        items.append(f'{spaces}- {text}')
                    return '\n'.join(items)
                else:
                    return str(data)

            def pretty_json(match: re.Match) -> str:
                raw = match.group(0)
                try:
                    parsed = json.loads(raw)
                    return dict_to_pretty(parsed)
                except Exception:
                    return raw

            text = json_pattern.sub(pretty_json, text)

        # 4. Очистка и нормализация текста
        lines = text.splitlines()
        cleaned_lines = []

        for line in lines:
            line = line.rstrip()  # Убираем пробелы справа
            if clean_for_code_block:
                # Для code block сохраняем левые отступы
                line = line
            else:
                # Для обычного текста убираем лишние пробелы слева
                line = line.lstrip()

            if line or (cleaned_lines and cleaned_lines[-1] != ''):
                cleaned_lines.append(line)

        # 5. Оптимизация пустых строк
        final_lines = []
        empty_line_count = 0
        max_empty_lines = 1 if clean_for_code_block else 2

        for line in cleaned_lines:
            if not line:
                empty_line_count += 1
                if empty_line_count <= max_empty_lines:
                    final_lines.append(line)
            else:
                empty_line_count = 0
                final_lines.append(line)

        result = '\n'.join(final_lines).strip()

        # 6. Дополнительная обработка для code block
        if clean_for_code_block:
            # Удаляем слишком длинные последовательности одинаковых символов
            # (часто бывает в base64)
            result = re.sub(r'(.)\1{50,}', r'\1\1\1...', result)

            lines = result.splitlines()
            trimmed_lines = []
            for line in lines:
                if len(line) > 1000:
                    line = line[:1000] + '...'
                trimmed_lines.append(line)
            result = '\n'.join(trimmed_lines)

        return result

    @staticmethod
    def normalize_email_datetime(
        email_date: datetime, msg_id: str
    ) -> datetime:
        """
        Приводит дату письма к локальной TZ и исправляет неверную зону,
        если результат попадает в будущее.
        """
        now_local = timezone.now()
        local_tz = ZoneInfo(settings.TIME_ZONE)
        time_diff_threshold = timedelta(minutes=30)

        # Если в письме нет TZ — считаем UTC
        if email_date.tzinfo is None:
            email_date = email_date.replace(tzinfo=timezone.utc)

        # Преобразовали дату в текущую TZ проекта
        email_local = email_date.astimezone(local_tz)

        if email_local <= now_local:
            return email_local

        # Если попали в будущее — пробуем заменить на временную зону проекта:
        candidate_time = email_date.replace(tzinfo=local_tz)
        candidate_local = candidate_time.astimezone(local_tz)

        if abs(candidate_local - now_local) <= time_diff_threshold:
            incident_manager_logger.warning(
                f'Письмо {msg_id}: дата {email_date.astimezone(local_tz)} '
                'была в будущем. Исправлено на '
                f'{candidate_local.astimezone(local_tz)} с использованием '
                f'локальной TZ {settings.TIME_ZONE}.'
            )
            return candidate_local

        return email_local
