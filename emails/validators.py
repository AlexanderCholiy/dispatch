import email
import os
import re
from datetime import datetime
from email import header, message
from email.utils import getaddresses
from typing import Optional

from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError

from core.constants import INCIDENT_DIR, SUBFOLDER_DATE_FORMAT

from .constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_PREFIXES,
    MAX_ATTACHMENT_SIZE,
    MAX_EMAIL_LEN,
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
        """Нормализуем список e-mail адресов из заголовков письма."""
        parsed = getaddresses(to_recipients)
        intermediate = [addr.strip() for _, addr in parsed if addr]

        email_regex = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

        emails = []
        for addr in intermediate:
            if (
                len(addr) <= MAX_EMAIL_LEN
                and email_regex.match(addr)
                and addr not in emails
            ):
                emails.append(addr)

        return emails

    def prepare_text_from_html(self, html_body_text: str) -> str:
        """Преобразует HTML в чистый текст, сохраняя ссылки."""

        if not html_body_text:
            return ''

        # Проверяем: это действительно HTML, а не просто текст с <https://...>
        is_html = bool(re.search(r'</\w+>', html_body_text))

        if is_html:
            soup = BeautifulSoup(html_body_text, 'lxml')

            # Заменим <a>теги их текстом + ссылкой:
            for a in soup.find_all('a'):
                href = a.get('href')
                if href:
                    a.replace_with(f'{a.get_text(strip=True)} ({href})')

            text = soup.get_text(strip=True)
        else:
            text = html_body_text.strip()

        text = re.sub(
            r'(https?://[^\s<>{}]+)\s*\n\s*([^\s<>{}]+)',
            lambda m: m.group(1) + m.group(2),
            text,
            flags=re.MULTILINE
        )

        # Убираем обёртку в угловых скобках: <https://...> → https://...
        text = re.sub(r'<(https?://[^>\s]+)>', r'\1', text)

        # Убираем случайные пробелы внутри URL
        text = re.sub(
            r'https?://\S*\s+\S*', lambda m: m.group(0).replace(' ', ''), text
        )

        return text

    def prepare_text_from_bytes(self, msg: message.Message) -> str:
        charset = msg.get_content_charset() or 'utf-8'
        return (
            msg.get_payload(decode=True).decode(charset, errors='replace')
            .strip()
        )

    def save_email_attachments(
        self,
        email_date: datetime,
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

        file_dir: str = os.path.join(
            INCIDENT_DIR,
            email_date.strftime(SUBFOLDER_DATE_FORMAT)
        )
        os.makedirs(file_dir, exist_ok=True)
        filepath = os.path.join(file_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(part.get_payload(decode=True))
