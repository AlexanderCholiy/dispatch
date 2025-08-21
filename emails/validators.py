import email
import os
from datetime import datetime
from email import header, message
from typing import Optional

import chardet
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError

from core.constants import INCIDENT_DIR, SUBFOLDER_DATE_FORMAT

from .constants import (
    ALLOWED_MIME_PREFIXES, MAX_ATTACHMENT_SIZE, ALLOWED_EXTENSIONS
)


class EmailValidator:

    def prepare_msg_id(self, msg_id: str) -> str:
        msg_id = msg_id.strip()
        return self.prepare_text_from_encode(msg_id).split(' ')[-1]

    def prepare_text_from_encode(self, original_text: str) -> str:
        decoded_words = header.decode_header(original_text)
        email_filename = ''.join(
            str(
                word, encoding if encoding else 'utf-8', errors='replace'
            ) if isinstance(word, bytes) else word
            for word, encoding in decoded_words
        )
        return email_filename

    def prepare_subject_from_bytes(
        self, subject: bytes | str, encoding: Optional[str]
    ) -> str:
        if isinstance(subject, bytes):
            try:
                email_subject = subject.decode(
                    encoding or 'utf-8', errors='replace'
                )
            except LookupError:
                email_subject = subject.decode('utf-8', errors='replace')
            return email_subject
        return subject

    def prepare_email_from(self, email_from_original: header.Header) -> str:
        email_from_parser: str = email.utils.parseaddr(email_from_original)[-1]
        email_from = email_from_parser if email_from_parser else (
            str(email_from_original)
            .split()[-1]
        )
        return email_from

    def prepare_email_to(self, to_recipients: list[str]) -> list[str]:
        return [
            self.prepare_msg_id(
                (to_recipient.replace('<', '').replace('>', '').strip())
            )
            for to_recipient in to_recipients
        ]

    def prepare_text_from_html(self, html_body_text: str) -> str:
        soup = BeautifulSoup(html_body_text, 'lxml')
        body_text = (
            soup.get_text(separator='\n').strip()
        )
        return body_text

    def prepare_text_from_bytes(self, byte_body_text: bytes) -> str:
        result: dict = chardet.detect(byte_body_text)
        encoding = result.get('encoding') or 'utf-8'
        body_text = (
            byte_body_text.decode(encoding, errors='replace').strip()
        )
        return body_text

    def save_email_attachments(
        self,
        email_data: datetime,
        filename: str,
        part: message.Message
    ):
        """
        Сохранение вложений из почты, с проверкой типов файлов.

        Raises:
            ValidationError: не допустимый тип файла.
        """
        content_type = part.get_content_type()
        payload = part.get_payload(decode=True)
        file_size = len(payload)
        ext = os.path.splitext(filename)[1].lower()

        if not any(
            content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES
        ) and ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f'Недопустимый тип файла {filename} ({content_type})')

        if file_size > MAX_ATTACHMENT_SIZE:
            raise ValidationError(
                f'Файл {filename} превышает max размер '
                f'{MAX_ATTACHMENT_SIZE / (1024 * 1024):.1f} MB'
            )

        subfolder_dir: str = os.path.join(
            INCIDENT_DIR,
            email_data.strftime(SUBFOLDER_DATE_FORMAT)
        )
        os.makedirs(subfolder_dir, exist_ok=True)
        filepath = os.path.join(subfolder_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(part.get_payload(decode=True))
