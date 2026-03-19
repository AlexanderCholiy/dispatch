import imaplib
import time

from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
)

from core.constants import MIN_WAIT_SEC_WITH_CRITICAL_EXC
from core.loggers import email_parser_logger
from core.utils import run_with_timeout_process
from emails.email_parser import email_parser


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'
    mailbox_map = {
        'inbox': email_parser.inbox_folder_name,
        'sent': email_parser.sent_folder_name,
    }

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            '--mailbox',
            type=str,
            choices=self.mailbox_map.keys(),
            help=(
                'Выбор почтовой папки. '
                f'Допустимые значения: {", ".join(self.mailbox_map.keys())}.'
            )
        )

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

        last_error_type = None

        min_timeout = 600  # 10 минут
        max_timeout = 1200  # 20 минут
        timeout_step = 300
        reserve_sec = 30
        current_timeout = min_timeout

        while True:
            err = None

            start_time = time.time()

            try:
                run_with_timeout_process(
                    email_parser.fetch_unread_emails,
                    func_timeout=max_timeout + reserve_sec,
                    mailbox=mailbox_name,
                    imap_ssl_timeout=current_timeout,
                )
            except KeyboardInterrupt:
                return
            except TimeoutError:
                # Плавное увеличение таймаута при ошибке:
                current_timeout = min(
                    current_timeout + timeout_step, max_timeout
                )
                email_parser_logger.warning(
                    'IMAP timeout. Устанавливаем новый таймаут: '
                    f'{current_timeout} секунд.'
                )
            except imaplib.IMAP4.abort:
                email_parser_logger.debug(
                    'Соединение с IMAP-сервером неожиданно закрылось'
                )
            except Exception as e:
                email_parser_logger.critical(e, exc_info=True)
                err = e
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
                # Адаптируем таймаут под фактическое время:
                elapsed = time.time() - start_time
                new_timeout = int(elapsed + reserve_sec)
                calculated_timeout = max(
                    min_timeout, min(new_timeout, max_timeout)
                )

                email_parser_logger.debug(
                    f'Установлен новый таймаут: {current_timeout} сек.'
                )

                current_timeout = calculated_timeout

            finally:
                if err is not None and last_error_type != type(err).__name__:
                    last_error_type = type(err).__name__
