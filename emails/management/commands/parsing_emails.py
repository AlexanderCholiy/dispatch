import imaplib
import time

from django.core.management.base import (
    BaseCommand,
    CommandParser,
    CommandError,
)

from core.constants import (
    EMAIL_LOG_ROTATING_FILE,
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
)
from core.loggers import LoggerFactory
from core.tg_bot import tg_manager
from core.utils import run_with_timeout_process
from emails.email_parser import email_parser

email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


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
            email_managment_logger.critical(err_msg)
            raise CommandError(err_msg)

        mailbox_name = self.mailbox_map[mailbox]

        tg_manager.send_startup_notification(__name__)

        first_success_sent = False
        had_errors_last_time = False
        last_error_type = None

        min_timeout = 300  # 5 минут
        max_timeout = 900  # 15 минут
        timeout_step = 30
        reserve_sec = 30
        current_timeout = min_timeout

        while True:
            err = None
            error_count = 0
            total_operations = 0

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
                email_managment_logger.warning(
                    'IMAP timeout. Устанавливаем новый таймаут: '
                    f'{current_timeout} секунд.'
                )
            except imaplib.IMAP4.abort:
                email_managment_logger.debug(
                    'Соединение с IMAP-сервером неожиданно закрылось'
                )
            except Exception as e:
                email_managment_logger.critical(e, exc_info=True)
                err = e
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
                # Адаптируем таймаут под фактическое время:
                elapsed = time.time() - start_time
                new_timeout = int(elapsed + reserve_sec)
                calculated_timeout = max(
                    min_timeout, min(new_timeout, max_timeout)
                )

                email_managment_logger.debug(
                    f'Установлен новый таймаут: {current_timeout} сек.'
                )

                current_timeout = calculated_timeout

                if not first_success_sent and not error_count:
                    tg_manager.send_first_success_notification(__name__)
                    first_success_sent = True

                if error_count and not had_errors_last_time:
                    tg_manager.send_warning_counter_notification(
                        __name__, error_count, total_operations
                    )

                had_errors_last_time = error_count > 0

            finally:
                if err is not None and last_error_type != type(err).__name__:
                    tg_manager.send_error_notification(__name__, err)
                    last_error_type = type(err).__name__
