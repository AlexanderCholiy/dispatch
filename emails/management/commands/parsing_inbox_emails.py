import time

from django.core.management.base import BaseCommand

from core.constants import (
    EMAIL_LOG_ROTATING_FILE,
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
)
from core.loggers import LoggerFactory
from core.tg_bot import tg_manager
from emails.email_parser import email_parser

email_managment_logger = LoggerFactory(
    __name__, EMAIL_LOG_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Запись писем с указанной почты в базу данных.'

    def handle(self, *args, **kwargs):
        tg_manager.send_startup_notification(__name__)

        first_success_sent = False
        had_errors_last_time = False
        last_error_type = None

        while True:
            err = None
            error_count = 0
            total_operations = 0

            try:
                email_parser.fetch_unread_emails(
                    mailbox=email_parser.inbox_folder_name)
            except KeyboardInterrupt:
                return
            except Exception as e:
                email_managment_logger.critical(e, exc_info=True)
                err = e
                time.sleep(MIN_WAIT_SEC_WITH_CRITICAL_EXC)
            else:
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
