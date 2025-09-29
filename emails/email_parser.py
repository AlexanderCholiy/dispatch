import email
import hashlib
import imaplib
import json
import os
import re
from datetime import datetime, timedelta
from email import header, message
from imaplib import IMAP4
from typing import Any, List, Optional, Tuple, Union

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from requests.exceptions import RequestException

from core.constants import API_STATUS_EXCEPTIONS, EMAIL_LOG_ROTATING_FILE
from core.exceptions import ApiServerError, ApiTooManyRequests
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.utils import Config
from core.wraps import min_wait_timer, timer
from emails.models import EmailErr, EmailFolder, EmailMessage
from incidents.utils import IncidentManager
from yandex_tracker.exceptions import YandexTrackerAuthErr
from yandex_tracker.utils import YandexTrackerManager, yt_manager

from .utils import EmailManager
from .validators import EmailValidator

email_parser_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


email_parser_config = {
    'PARSING_EMAIL_LOGIN': os.getenv('PARSING_EMAIL_LOGIN'),
    'PARSING_EMAIL_PSWD': os.getenv('PARSING_EMAIL_PSWD'),
    'PARSING_EMAIL_SERVER': os.getenv('PARSING_EMAIL_SERVER'),
    'PARSING_EMAIL_PORT': os.getenv('PARSING_EMAIL_PORT', 993),
    'PARSING_EMAIL_SENT_FOLDER_NAME': os.getenv('PARSING_EMAIL_SENT_FOLDER_NAME'),  # noqa: E501
}

Config.validate_env_variables(email_parser_config)


class EmailParser(EmailValidator, EmailManager, IncidentManager):

    inbox_folder_name = 'INBOX'

    def __init__(
        self,
        email_login: str,
        email_pswd: str,
        email_server: str,
        email_port: str | int,
        yt_manager: Optional[YandexTrackerManager],
        sent_folder_name: str,
    ):
        self.email_login = email_login
        self.email_pswd = email_pswd
        self.email_server = email_server
        self.email_port = int(email_port)

        self.yt_manager = yt_manager

        self.sent_folder_name = sent_folder_name

    def _find_emails_by_date(
        self, today: datetime, check_days: int, mail: imaplib.IMAP4_SSL
    ) -> list[bytes]:
        start_date = today - timedelta(days=check_days)
        end_date = today + timedelta(days=1)

        date_since = start_date.strftime('%d-%b-%Y')
        date_before = end_date.strftime('%d-%b-%Y')

        search_query = f'(SINCE {date_since} BEFORE {date_before})'

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
        start_date = today - timedelta(days=check_days)
        end_date = today + timedelta(days=1)

        date_since = start_date.strftime('%d-%b-%Y')
        date_before = end_date.strftime('%d-%b-%Y')

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
        Для сообщений отправленных из формы, надо найти json и из него выбрать
        email отправителя и получателей.

        Функция находит все JSON-блоки в тексте и возвращает список словарей и
        остальной текст.
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

    def _is_first_email(
        self,
        in_reply_to: Optional[str],
        references: Optional[list[str]],
        message_id: Optional[str] = None,
        our_message_ids: Optional[set[str]] = None,
    ) -> bool:
        """
        Определяет, является ли письмо первым для нас в цепочке.

        Args:
            in_reply_to: заголовок In-Reply-To
            references: список References
            message_id: текущий message-id письма
            our_message_ids: set всех message_id, которые уже есть в нашей
            системе
        """

        # Если нет цепочки ссылок:
        if not in_reply_to and not references:
            return True

        # References пустой или None:
        if not references:
            return True

        # Если In-Reply-To указывает на самого себя:
        if (
            message_id
            and in_reply_to
            and in_reply_to.strip() == message_id.strip()
        ):
            return True

        # Если In-Reply-To auto-сгенерированный или пустой мусор:
        if in_reply_to and (
            in_reply_to.lower().startswith('<auto-')
            or in_reply_to.lower() in {'<null>', '<0>', '<none>'}
        ):
            return True

        # References состоит из одного элемента и он совпадает с message_id:
        if (
            message_id
            and references
            and len(references) == 1
            and references[0].strip() == message_id.strip()
        ):
            return True

        # Проверяем, есть ли References на письма нашей системы:
        if our_message_ids and references:
            for ref in references:
                if ref.strip() in our_message_ids:
                    return False  # Письмо является ответом на наше предыдущее
            # Ни одна ссылка не принадлежит нашей системе, значит для нас оно
            # первое:
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

        if not self.yt_manager or not subject:
            return result

        tracker_headers = [
            'X-Yandex-Tracker-Mail-Type',
            'X-Yandex-Tracker-Env',
            'X-Tracker-Issue-Key',
            'X-Tracker-Comment-Id'
        ]

        if any(header in msg for header in tracker_headers):
            matches = re.findall(
                rf'{self.yt_manager.queue}-\d+', subject)
            result = True if matches else False

        return result

    def fetch_emails_in_chunks(
        self,
        mail: IMAP4,
        email_ids: List[Union[bytes, str]],
        chunk_size: int = 500
    ) -> List[Tuple[bytes, Any]]:
        """
        Получает письма чанками, чтобы не перегружать IMAP сервер.

        Args:
            mail (IMAP4): активное IMAP4 соединение
            email_ids (list): список ID писем (bytes или str)
            chunk_size (int): размер чанка для FETCH

        Returns:
            list: список сообщений в сыром виде от imaplib
        """
        normalized_ids = [
            id_.decode() if isinstance(id_, bytes) else str(id_)
            for id_ in email_ids
        ]

        total = len(normalized_ids)
        all_messages = []

        for i in range(0, total, chunk_size):
            chunk = normalized_ids[i:i + chunk_size]
            id_range = ','.join(chunk)

            try:
                status, messages = mail.fetch(id_range, '(RFC822)')
            except KeyboardInterrupt:
                raise
            except (imaplib.IMAP4.abort, ConnectionResetError, OSError):
                continue
            except Exception as e:
                email_parser_logger.error(
                    'Ошибка при FETCH (ids=%s): %s', id_range, str(e)
                )
                continue

            if status != 'OK':
                email_parser_logger.warning(
                    f'Ошибка при получении писем (status={status})',
                )
                continue

            all_messages.extend(messages)

        return all_messages

    @property
    def folders_list(self):
        """Список доступных папок в почте."""
        with imaplib.IMAP4_SSL(self.email_server, self.email_port) as mail:
            mail.login(self.email_login, self.email_pswd)
            _, folders = mail.list()
            return [
                imap_folder.decode() for imap_folder in folders
            ]

    @min_wait_timer(email_parser_logger)
    @timer(email_parser_logger)
    def fetch_unread_emails(
        self,
        check_days: int = 0,
        check_err_days: int = 7,
        mailbox: str = inbox_folder_name,
        imap_ssl_timeout: int = 600
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
        if mailbox == self.inbox_folder_name:
            folder, _ = EmailFolder.objects.get_or_create(
                name='INBOX',
                defaults={
                    'description': 'Папка входящих email (по умолчанию)'
                }
            )

        elif mailbox == self.sent_folder_name:
            folder, _ = EmailFolder.objects.get_or_create(
                name='SENT',
                defaults={
                    'description': 'Папка исходящих email (по умолчанию)'
                }
            )
        else:
            folder, _ = EmailFolder.objects.get_or_create(name=mailbox)

        today = timezone.now()
        err_days_ago = today - timedelta(
            days=max((check_days + 1), (check_err_days + 1))
        )

        with imaplib.IMAP4_SSL(
            self.email_server,
            self.email_port,
            timeout=imap_ssl_timeout
        ) as mail:
            mail.login(self.email_login, self.email_pswd)
            mail.select(mailbox, readonly=True)

            err_msg_ids: set[str] = set(
                EmailErr.objects
                .filter(incert_date__gte=err_days_ago, incert_date__lte=today)
                .values_list('email_msg_id', flat=True)
            )

            archive_msg_ids: set[str] = set(
                EmailMessage.objects
                .filter(email_date__gte=err_days_ago, email_date__lte=today)
                .values_list('email_msg_id', flat=True)
            )

            new_emails_ids = (
                self._find_emails_by_date(today, check_days, mail)
            )

            found_emails_ids = self._find_email_by_id(
                err_msg_ids, mail, today, check_err_days
            )

            email_ids = list(set(new_emails_ids + found_emails_ids))
            messages = self.fetch_emails_in_chunks(mail, email_ids)

            parsed_messages = []
            for part in messages:
                if isinstance(part, tuple) and len(part) == 2:
                    msg_bytes = part[1]
                    if not msg_bytes:
                        continue
                    msg = email.message_from_bytes(msg_bytes)
                    parsed_messages.append(msg)

            email_err_msg_ids = []
            email_err_msg_ids_to_del = []
            email_msg_counter = 0

            total = len(parsed_messages)

            our_message_ids = set(
                EmailMessage.objects.all()
                .values_list('email_msg_id', flat=True)
            )

            for index, msg in enumerate(parsed_messages):

                PrettyPrint.progress_bar_debug(
                    index, total, f'Парсинг почты (папка {folder.name}):')
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
                    if email_subject and 'undeliverable mail' in (
                        email_subject.lower()
                    ):
                        continue

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
                                        filename
                                    )
                                except ValidationError as e:
                                    email_parser_logger.warning(e)
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
                                        filename
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
                    json_dicts = None
                    if email_body:
                        json_dicts, _ = EmailParser.parse_all_json_from_text(
                            email_body
                        )
                        email_body = EmailManager.normalize_text_with_json(
                            email_body)
                    else:
                        email_body = None

                    email_subject = EmailManager.normalize_text_with_json(
                        email_subject
                    ) if email_subject else None

                    is_first_email = self._is_first_email(
                        email_msg_reply_id,
                        email_msg_references,
                        email_msg_id,
                        our_message_ids
                    )

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
                        email_msg = self.add_email_message(
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
                            folder=folder,
                        )
                        self.add_incident_from_email(
                            email_msg, self.yt_manager
                        )
                        email_err_msg_ids_to_del.append(email_msg_id)
                    except KeyboardInterrupt:
                        raise
                    except IntegrityError:
                        email_err_msg_ids.append(email_msg_id)
                        email_parser_logger.error(
                            f'Ошибка добавления email: {email_msg_id}',
                            exc_info=True
                        )
                    except RequestException:
                        email_err_msg_ids.append(email_msg_id)
                        email_parser_logger.error(
                            f'Ошибка добавления email: {email_msg_id}',
                            exc_info=True
                        )
                    except (ApiTooManyRequests, ApiServerError) as e:
                        email_err_msg_ids.append(email_msg_id)
                        email_parser_logger.warning(e)
                    except YandexTrackerAuthErr as e:
                        email_err_msg_ids.append(email_msg_id)
                        email_parser_logger.critical(e)
                    except tuple(API_STATUS_EXCEPTIONS.values()) as e:
                        email_err_msg_ids.append(email_msg_id)
                        email_parser_logger.error(e)
                    except Exception:
                        invalid_data = {
                            'email_msg_id': email_msg_id,
                            'email_msg_reply_id': email_msg_reply_id,
                            'email_subject': email_subject,
                            'email_from': email_from,
                            'email_date': email_date,
                            'email_body': email_body,
                            'is_first_email': is_first_email,
                            'is_email_from_yandex_tracker': (
                                is_email_from_yandex_tracker),
                            'email_to': email_to,
                            'email_to_cc': email_to_cc,
                            'email_msg_references': email_msg_references,
                            'email_attachments_urls': email_attachments_urls,
                            'email_attachments_intext_urls': (
                                email_attachments_intext_urls
                            ),
                            'folder': folder,
                        }
                        email_err_msg_ids.append(email_msg_id)
                        email_parser_logger.exception(
                            f'Не валидные данные: {invalid_data}')

            if email_msg_counter:
                email_parser_logger.info(
                    f'Было найдено {email_msg_counter} новых сообщений '
                    f'в папке {folder.name}'
                )

            self.add_err_msg_bulk(email_err_msg_ids)
            self.del_err_msg_bulk(email_err_msg_ids_to_del)


email_parser = EmailParser(
    email_login=email_parser_config['PARSING_EMAIL_LOGIN'],
    email_pswd=email_parser_config['PARSING_EMAIL_PSWD'],
    email_server=email_parser_config['PARSING_EMAIL_SERVER'],
    email_port=email_parser_config['PARSING_EMAIL_PORT'],
    yt_manager=yt_manager,
    sent_folder_name=email_parser_config['PARSING_EMAIL_SENT_FOLDER_NAME'],
)
