import os
import re
import json
import html
from datetime import datetime
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.files import File
from django.db import DatabaseError, models, transaction
from django.utils import timezone

from core.constants import SUBFOLDER_DATE_FORMAT, SUBFOLDER_EMAIL_NAME
from core.models import Attachment

from .models import (
    EmailAttachment,
    EmailErr,
    EmailInTextAttachment,
    EmailMessage,
    EmailReference,
    EmailTo,
    EmailToCC,
)


class EmailManager:

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
    def valid_email_file_path(
        attachments: EmailAttachment | EmailInTextAttachment
    ) -> list[str]:
        files = []
        for attachment in attachments:
            relative_file_path = Path(attachment.file_url.name)
            file_path = os.path.join(
                settings.MEDIA_ROOT, str(relative_file_path)
            )

            if os.path.exists(file_path):
                files.append(file_path)
            else:
                try:
                    attachment.delete()
                except DatabaseError:
                    pass

        return files

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
                        items.append(f'{spaces}{key}: {dict_to_pretty(value, indent + 1)}')
                    return '\n'.join(items)
                elif isinstance(data, list):
                    items = []
                    for item in data:
                        items.append(f'{spaces}- {dict_to_pretty(item, indent + 1)}')
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
