import email
import hashlib
import imaplib
import json
import re
import os
from datetime import datetime, timedelta
from email import header, message
from typing import Optional

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import IntegrityError

from core.constants import EMAIL_LOG_ROTATING_FILE, SUBFOLDER_DATE_FORMAT
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from emails.models import EmailErr, EmailMessage
from yandex_tracker.constants import YT_QUEUE

from .validators import EmailValidator
from .utils import EmailManager

email_parser_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


class EmailParser(EmailValidator, EmailManager):

    def __init__(
        self,
        email_login: str,
        email_pswd: str,
        email_server: str,
        email_port: str | int,
    ):
        self.email_login = email_login
        self.email_pswd = email_pswd
        self.email_server = email_server
        self.email_port = int(email_port)

    def _find_emails_by_date(
        self, today: datetime, check_days: int, mail: imaplib.IMAP4_SSL
    ) -> list[bytes]:
        days_ago: datetime = today - timedelta(days=check_days)

        date_before: str = today.strftime("%d-%b-%Y")
        date_since = days_ago.strftime("%d-%b-%Y")

        search_query: str = (
            f'(SINCE "{date_since}" BEFORE "{date_before}")'
        ) if check_days > 1 else f'SINCE "{date_before}"'

        status, messages = mail.search(None, search_query)
        if status != 'OK' or not messages[0]:
            return []

        return messages[0].split()

    def _find_email_by_id(
        self,
        message_ids: set[str],
        mail: imaplib.IMAP4_SSL,
        today: datetime,
        check_days: int
    ) -> list[bytes]:
        days_ago: datetime = today - timedelta(days=check_days)
        date_before: str = today.strftime("%d-%b-%Y")
        date_since = days_ago.strftime("%d-%b-%Y")

        found_email_ids = []
        total = len(message_ids)
        for index, message_id in enumerate(message_ids):
            PrettyPrint.progress_bar_error(
                index, total, 'Поиск писем из EmailErr:')
            search_query = (
                f'HEADER Message-ID "{message_id}" '
                f'SINCE "{date_since}" BEFORE "{date_before}"'
            )
            status, messages = mail.search(None, search_query)

            if status == 'OK':
                email_ids = messages[0].split()
                filtered_ids = [
                    email_id for email_id in email_ids if email_id != b''
                ]

                if filtered_ids:
                    found_email_ids.extend(filtered_ids)

        return found_email_ids

    @staticmethod
    def parse_all_json_from_text(text: str) -> tuple[list[dict], str]:
        """
        Находит все JSON-блоки в тексте.
        Возвращает список словарей и остальной текст.
        """
        json_blocks = []
        remaining_text = text
        pattern = re.compile(r'\{.*?\}', re.DOTALL)

        while True:
            match = pattern.search(remaining_text)
            if not match:
                break

            candidate = match.group()
            try:
                json_dict = json.loads(candidate)
                json_blocks.append(json_dict)
                remaining_text = (
                    remaining_text[:match.start()]
                    + remaining_text[match.end():]
                )
            except json.JSONDecodeError:
                remaining_text = remaining_text[match.end():]

        human_text = remaining_text.replace('\n\n', '\n').strip()
        return json_blocks, human_text

    @staticmethod
    def build_human_readable_description(text: str) -> str:
        """
        Преобразует письмо в человекочитаемый вид:
        - JSON превращается в список "ключ: значение"
        - Остальной текст добавляется внизу
        """
        json_blocks, human_text = EmailParser.parse_all_json_from_text(text)

        lines = []
        for json_dict in json_blocks:
            for k, v in json_dict.items():
                lines.append(f'{k}: {v}')
            lines.append('')

        if human_text:
            if lines:
                lines.append('')
            lines.append(human_text)

        return '\n'.join(lines)

    def _is_first_email(
        self, in_reply_to: Optional[str], references: Optional[list[str]]
    ) -> bool:
        """
        Определяет, является ли письмо первым в переписке.
        Учитывает наличие заголовков In-Reply-To и References.
        """
        if not in_reply_to and not references:
            return True

        # Иногда встречается auto-сгенерированный In-Reply-To:
        if in_reply_to and in_reply_to.lower().startswith('<auto-'):
            return True

        return False

    def _is_from_yandex_tracker(
        self, msg: message.Message, subject: Optional[str]
    ) -> bool:
        """
        Проверяем наличие заголовков, специфичных для Yandex
        Tracker.
        Если письмо было отправленно из Yandex Tracker, надо
        убедиться что оно соответствует нашей очереди.
        """
        result = False
        tracker_headers = [
            'X-Yandex-Tracker-Mail-Type',
            'X-Yandex-Tracker-Env',
            'X-Tracker-Issue-Key',
            'X-Tracker-Comment-Id'
        ]
        if not subject:
            return result

        if any(header in msg for header in tracker_headers):
            matches = re.findall(
                rf'{YT_QUEUE}-\d+', subject)
            result = True if matches else False

        return result

    def fetch_unread_emails(
        self,
        check_days: int = 0,
        check_err_days: int = 7,
        mailbox: str = 'INBOX',
    ):
        """
        Парсинг писем для получения непрочитанных сообщений и запись их в БД.

        Args:
            check_days (int, optional):
                Количество дней для проверки непрочитанных писем.
                По умолчанию 0 (с текущего дня).
            check_err_days (int, optional):
                Количество дней для проверки ошибок в письмах.
                По умолчанию 7 (недельной давности).
            mailbox (str):
                Папка для проверки новых писем.
                По умолчанию стандартная папка входящих писем INBOX.
        """

        today = timezone.now()
        err_days_ago = today - timedelta(days=check_err_days)

        with imaplib.IMAP4_SSL(self.email_server, self.email_port) as mail:
            mail.login(self.email_login, self.email_pswd)
            mail.select(mailbox, readonly=True)

            err_msg_ids: list[str] = set(
                EmailErr.objects
                .filter(incert_date__gte=err_days_ago, incert_date__lte=today)
                .values_list('email_msg_id', flat=True)
            )

            archive_msg_ids: list[str] = set(
                EmailMessage.objects
                .filter(email_date__gte=err_days_ago, email_date__lte=today)
                .values_list('email_msg_id', flat=True)
            )

            new_emails_ids = (
                self._find_emails_by_date(datetime.now(), check_days, mail)
            )

            found_emails_ids = self._find_email_by_id(
                err_msg_ids, mail, today, check_err_days
            )

            email_ids = list(
                set(new_emails_ids + found_emails_ids))
            total = len(email_ids)

            id_range = b','.join(email_ids)
            status, messages = mail.fetch(id_range, '(RFC822)')

            if status != 'OK':
                email_parser_logger.warning(
                    'Ошибка при получении писем (status=%s, ids=%s)',
                    status, id_range.decode()
                )
                return

            parsed_messages = []
            for part in messages:
                if isinstance(part, tuple) and len(part) == 2:
                    msg_bytes = part[1]
                    if not msg_bytes:
                        continue
                    msg = email.message_from_bytes(msg_bytes)
                    parsed_messages.append(msg)

            email_err_msg_ids = []
            email_msg_counter = 0

            for index, msg in enumerate(parsed_messages):

                PrettyPrint.progress_bar_debug(index, total, 'Парсинг почты:')
                email_msg_id = None

                try:
                    email_msg_id: str = self.prepare_msg_id(msg['Message-ID'])

                    if (
                        email_msg_id in archive_msg_ids
                        and email_msg_id not in err_msg_ids
                    ):
                        continue
                    email_msg_counter += 1

                    subject_header = msg.get('Subject')
                    if subject_header is not None:
                        subject, encoding_sj = header.decode_header(
                            subject_header)[0]
                    else:
                        subject, encoding_sj = None, None

                    encoding = (
                        msg.get_content_charset() or encoding_sj or 'utf-8'
                    )

                    email_subject: str = self.prepare_subject_from_bytes(
                        subject, encoding
                    )

                    email_from: str = self.prepare_email_from(msg['From'])

                    cleaned_date_string = msg.get('Date').split(' (')[0]
                    try:
                        email_date: datetime = datetime.strptime(
                            cleaned_date_string, '%a, %d %b %Y %H:%M:%S %z'
                        )
                    except ValueError:
                        email_date: datetime = datetime.strptime(
                            cleaned_date_string, '%d %b %Y %H:%M:%S %z'
                        )

                    email_msg_reply_id: Optional[str] = self.prepare_msg_id(
                        msg.get('In-Reply-To')
                    ) if msg.get('In-Reply-To') is not None else None

                    email_to: list[str] = (
                        self.prepare_email_to(msg.get_all('To', []))
                    )

                    email_to_cc: list[str] = (
                        self.prepare_email_to(msg.get_all('Cc', []))
                        + self.prepare_email_to(msg.get_all('Bcc', []))
                    )

                    references: Optional[str] = msg.get('References')
                    email_msg_references = [
                        self.prepare_msg_id(
                            f'<{reference}'
                        ) for reference in references.split('<') if reference
                    ] if references else []

                    email_attachments_urls = []
                    email_attachments_intext_urls = []
                    email_body = None

                    save_file_err = False
                    if msg.is_multipart():
                        for sub_index, part in enumerate(msg.walk()):
                            email_msg_id_hash: str = (
                                hashlib.md5(email_msg_id.encode()).hexdigest()
                            )
                            unique_filename_part: str = (
                                f'{email_date.strftime("%H%M%S")}__'
                                f'{email_msg_id_hash}__{sub_index}__'
                            )
                            content_type: Optional[str] = (
                                part.get_content_type()
                            )
                            content_disposition: Optional[str] = (
                                part.get_content_disposition()
                            )

                            if (
                                content_disposition and (
                                    content_disposition == 'attachment'
                                )
                            ):
                                original_file_name: Optional[str] = (
                                    part.get_filename()
                                )
                                if not original_file_name:
                                    continue

                                email_filename: str = (
                                    self.prepare_text_from_encode(
                                        original_file_name
                                    )
                                )
                                try:
                                    filename = (
                                        f'{unique_filename_part}'
                                        f'{email_filename}'
                                    )
                                    self.save_email_attachments(
                                        email_date, filename, part
                                    )
                                    email_attachments_urls.append(
                                        os.path.join(
                                            email_date.strftime(
                                                SUBFOLDER_DATE_FORMAT
                                            ), filename
                                        )
                                    )
                                except ValidationError:
                                    email_parser_logger.warning(
                                        f'Недопустимый файл {filename} '
                                        f'для email: {email_msg_id}'
                                    )
                                except OSError:
                                    save_file_err = True

                            elif (
                                content_type and content_type.startswith(
                                    'image/'
                                )
                            ):
                                try:
                                    filename = (
                                        f'{unique_filename_part}'
                                        f'intext.{content_type.split("/")[1]}'
                                    )
                                    self.save_email_attachments(
                                        email_date,
                                        filename,
                                        part,
                                    )
                                    email_attachments_intext_urls.append(
                                        os.path.join(
                                            email_date.strftime(
                                                SUBFOLDER_DATE_FORMAT
                                            ), filename
                                        )
                                    )
                                except ValidationError as e:
                                    email_parser_logger.warning(e)
                                except OSError:
                                    save_file_err = True

                            elif (
                                content_type and content_type in (
                                    'text/plain', 'text/html'
                                )
                            ):
                                payload = part.get_payload(decode=True)
                                email_body = self.prepare_text_from_bytes(
                                    payload
                                )
                                if content_type == 'text/html':
                                    email_body = self.prepare_text_from_html(
                                        email_body
                                    ).replace(email_subject or '', '').strip()
                    else:
                        html_body_text = msg.get_payload(decode=True).decode(
                            encoding=encoding
                        )
                        email_body = self.prepare_text_from_html(
                            html_body_text)

                    if save_file_err:
                        email_parser_logger.warning((
                            'Ошибка при сохранении файла для email: ',
                            email_msg_id
                        ))
                except KeyboardInterrupt:
                    raise
                except Exception:
                    if email_msg_id:
                        email_parser_logger.exception(
                            f'Ошибка при обрабоке email: {email_msg_id}'
                        )
                        email_err_msg_ids.append(email_msg_id)
                else:
                    if email_body:
                        json_dicts, _ = EmailParser.parse_all_json_from_text(
                            email_body
                        )
                        email_body = (
                            EmailParser.build_human_readable_description(
                                email_body
                            )
                        )
                    else:
                        email_body = None

                    email_subject = (
                        EmailParser.build_human_readable_description(
                            email_subject
                        )
                    ) if email_subject else None

                    is_first_email = self._is_first_email(
                        email_msg_reply_id, email_msg_references)

                    if json_dicts and is_first_email:
                        email_from_i = json_dicts[0].get(
                            'E-mail для обратной связи')

                        email_cc_i = []
                        for key, value in json_dicts[0].items():
                            if (
                                isinstance(key, str)
                                and key.startswith(
                                    'E-mail наблюдателя по заявке'
                                )
                            ):
                                email_cc_i.append(value)

                        email_to_cc = (
                            email_cc_i + email_to_cc
                        ) if email_cc_i else email_to_cc
                        email_from = (
                            email_from_i
                        ) if email_from_i else email_from

                    is_email_from_yandex_tracker = (
                        self._is_from_yandex_tracker(msg, email_subject)
                    )

                    try:
                        self.add_email_message(
                            email_msg_id=email_msg_id,
                            email_msg_reply_id=email_msg_reply_id,
                            email_subject=email_subject,
                            email_from=email_from,
                            email_date=email_date,
                            email_body=email_body,
                            is_first_email=is_first_email,
                            is_email_from_yandex_tracker=(
                                is_email_from_yandex_tracker
                            ),
                            was_added_2_yandex_tracker=(
                                is_email_from_yandex_tracker
                            ),
                            email_to=email_to,
                            email_to_cc=email_to_cc,
                            email_msg_references=email_msg_references,
                            email_attachments_urls=email_attachments_urls,
                            email_attachments_intext_urls=(
                                email_attachments_intext_urls
                            ),
                        )
                    except IntegrityError:
                        email_err_msg_ids.append(email_msg_id)
                        email_parser_logger.debug(
                            f'Ошибка добавления email: {email_msg_id}'
                        )
            email_parser_logger.debug(
                f'Было найдено {email_msg_counter} новых сообщений'
            )
            self.add_err_msg_bulk(email_err_msg_ids)
