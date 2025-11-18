import email
import os
import re
import unicodedata
from datetime import datetime
from email import header, message
from email.utils import getaddresses
from typing import Optional

import html2text
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
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

    @staticmethod
    def normalize_invisible_spaces(text: Optional[str]) -> Optional[str]:
        """
        Приводит строку к нормальному виду:
        - заменяет все невидимые пробелоподобные символы на обычный пробел,
        - убирает лишние пробелы в начале/конце,
        - сводит повторяющиеся пробелы к одному.
        """
        if not text or not text.strip():
            return None

        # Нормализуем Unicode (чтобы объединить похожие символы)
        text = unicodedata.normalize('NFKC', text)

        # Заменяем все пробельные символы (в том числе NBSP, табуляции,
        # переводы строки) на обычный пробел
        text = re.sub(r'[\s\u00A0\u2000-\u200B\u202F\u205F\u3000]+', ' ', text)

        # Убираем пробелы в начале и конце
        return text.strip()

    def _add_reply_dividers(
        self,
        text: str,
        divider: str = '-----Original Message-----'
    ) -> str:
        """
        Добавляет разделитель перед строками, начинающимися с 'From:'.
        Разделитель вставляется только один раз подряд.
        """
        lines = text.splitlines()
        result = []
        just_inserted_divider = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith('From:') and 'Original Message' not in text:
                if not just_inserted_divider:
                    result.append(divider)
                    just_inserted_divider = True
            else:
                if stripped != '':
                    just_inserted_divider = False

            result.append(line)

        return '\n'.join(result)

    def prepare_text_from_html_bak(self, html: str) -> str:
        # 1) HTML → plain text (без markdown):
        h = html2text.HTML2Text()
        h.ignore_links = False        # оставляем ссылки
        h.ignore_images = True        # убираем картинки
        h.body_width = 0              # сохраняем переносы
        h.skip_internal_links = False  # ссылки как обычный текст
        h.single_line_break = False   # сохраняем переносы строк
        h.protect_links = True        # ссылки в скобках

        text = h.handle(html)

        # 2) Убираем markdown-символы:
        text = re.sub(r'[*_`#\[\]>-]', '', text)

        # 3) Добавляем разделители перед ответами:
        text = self._add_reply_dividers(text)

        return text

    def prepare_text_from_html(self, html: str) -> str:
        if not html:
            return ''

        soup = BeautifulSoup(html, 'lxml')
        for tag in soup(['style', 'script']):
            tag.decompose()
        for comment in soup.find_all(
            string=lambda text: isinstance(text, Comment)
        ):
            comment.extract()

        lines = []

        def walk(node):
            if isinstance(node, NavigableString):
                text = node.strip()
                if text:
                    lines.append(text)
            elif isinstance(node, Tag):
                # перенос строки для блочных элементов
                if node.name == 'br':
                    lines.append('\n')
                elif node.name in ['p', 'li', 'div', 'section', 'article']:
                    # добавляем переносы перед блоком
                    lines.append('\n')
                    # для li добавляем маркер
                    prefix = '- ' if node.name == 'li' else ''
                    if any(
                        isinstance(c, NavigableString) and c.strip()
                        for c in node.contents
                    ):
                        lines.append(prefix)

                # обработка ссылок
                if node.name == 'a' and node.get('href'):
                    text_a = node.get_text(strip=True)
                    if text_a:
                        lines.append(f'{text_a} ({node["href"]})')
                    return

                # рекурсивный обход детей
                for child in node.children:
                    walk(child)

                # перенос после блочных элементов
                if node.name in ['p', 'div', 'section', 'article']:
                    lines.append('\n')

        walk(soup.body or soup)

        # собираем текст, сохраняем переносы
        text = ''.join(lines)
        # убираем лишние пробелы перед переносами
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)

        text = self._add_reply_dividers(text)

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
