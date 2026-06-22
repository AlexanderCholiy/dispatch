import imaplib
import time

from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)

from core.constants import MIN_WAIT_SEC_WITH_CRITICAL_EXC
from core.loggers import email_parser_logger
from emails.email_parser import email_parser


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'
    mailbox_map = {
        'inbox': email_parser.inbox_folder_name,
        'sent': email_parser.sent_folder_name,
    }
    conn_timeout = 600

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            '--mailbox',
            type=str,
            choices=self.mailbox_map.keys(),
            help=(
                'Выбор почтовой папки. '
                f'Допустимые значения: {", ".join(self.mailbox_map.keys())}.'
            ),
        )

    def create_mail_connection(self, mailbox_name: str) -> imaplib.IMAP4_SSL:
        """Создает новое соединение, логинится и выбирает папку."""
        mail = None
        try:
            mail = imaplib.IMAP4_SSL(
                email_parser.email_server,
                email_parser.email_port,
                timeout=self.conn_timeout,
            )
            mail.login(email_parser.email_login, email_parser.email_pswd)
            mail.select(mailbox_name, readonly=True)

            email_parser_logger.debug(
                f'Успешное подключение к папке {mailbox_name}'
            )
            return mail
        except Exception as e:
            email_parser_logger.error(f'Ошибка при создании соединения: {e}')
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass
            raise

    def handle(self, *args, **kwargs):
        mailbox = (kwargs.get('mailbox') or '').strip().lower()

        if mailbox not in self.mailbox_map:
            err_msg = (
                f'Неверное значение --mailbox: {mailbox!r}. '
                f'Допустимые значения: {", ".join(self.mailbox_map.keys())}.'
            )
            email_parser_logger.critical(err_msg)
            raise CommandError(err_msg)

        mailbox_name = self.mailbox_map[mailbox]
        mail = None

        while True:

            if mail is None:
                try:
                    mail = self.create_mail_connection(mailbox_name)
                except Exception as conn_err:
                    email_parser_logger.exception(
                        f'Не удалось создать соединение: {conn_err}'
                    )
                    time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
                    continue

            try:
                email_parser.fetch_unread_emails(
                    mail=mail,
                    mailbox=mailbox_name,
                )

            except KeyboardInterrupt:
                return

            except TimeoutError:
                email_parser_logger.warning('Таймаут парсинга писем.')

                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except Exception:
                        pass

                mail = None

            except (
                imaplib.IMAP4.abort, imaplib.IMAP4.error, ConnectionResetError
            ) as e:
                email_parser_logger.error(
                    f'Ошибка соединения с почты сервером: {e}.'
                )

                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except Exception:
                        pass

                mail = None

            except Exception as e:
                email_parser_logger.exception(
                    f'Критическая ошибка парсинга почты: {e}'
                )

                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except Exception:
                        pass

                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
                mail = None
