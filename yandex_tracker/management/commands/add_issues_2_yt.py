import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min

from core.constants import (
    MIN_WAIT_SEC_WITH_CRITICAL_EXC,
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from core.wraps import min_wait_timer, timer
from emails.models import EmailMessage
from incidents.utils import IncidentManager
from yandex_tracker.utils import YandexTrackerManager, yt_manager

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление данных в YandexTracker.'

    min_seconds = 3

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
                total_operations, error_count = self.add_issues_2_yt(
                    yt_manager)
            except KeyboardInterrupt:
                return
            except Exception as e:
                yt_managment_logger.critical(e, exc_info=True)
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

    @min_wait_timer(yt_managment_logger, min_seconds)
    @timer(yt_managment_logger)
    def add_issues_2_yt(self, yt_manager: YandexTrackerManager):
        emails = (
            YandexTrackerManager.emails_for_yandex_tracker()
            .select_related('email_incident')
        )

        total = len(emails)
        error_count = 0

        if not emails:
            return total, error_count

        # Определяем первое письмо по дате для каждого инцидента:
        incident_ids = {e.email_incident for e in emails}

        first_emails = (
            EmailMessage.objects.filter(email_incident__in=incident_ids)
            .values('email_incident')
            .annotate(first_date=Min('email_date'))
        )

        first_email_map = {
            item['email_incident']: item['first_date'] for item in first_emails
        }

        # Разблокируем кастомные поля:
        fields = [
            yt_manager.database_global_field_id,
            yt_manager.emails_ids_global_field_id,
        ]
        for index, field_id in enumerate(fields):
            yt_manager.update_custom_field(
                field_id=field_id,
                readonly=False,
                hidden=False,
                visible=False,
            )

            if index < len(fields) - 1:
                time.sleep(self.min_seconds)

        for index, email in enumerate(emails):
            PrettyPrint().progress_bar_error(
                index, total, 'Обновление заявок в YandexTracker:'
            )
            incident = email.email_incident

            with transaction.atomic():
                if not incident.responsible_user:
                    incident.responsible_user = (
                        IncidentManager
                        .choice_dispatch_for_incident(yt_manager)
                    )
                    incident.save()

                try:
                    is_first = (
                        email.email_date <= first_email_map.get(incident.pk)
                    )
                    yt_manager.add_incident_to_yandex_tracker(email, is_first)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    error_count += 1
                    yt_managment_logger.exception(e)
                else:
                    email.was_added_2_yandex_tracker = True
                    email.save()

        # Блокируем кастомные поля обратно:
        for index, field_id in enumerate(fields):
            yt_manager.update_custom_field(
                field_id=field_id,
                readonly=True,
                hidden=False,
                visible=False,
            )

            if index < len(fields) - 1:
                time.sleep(self.min_seconds)

        yt_managment_logger.info(
            'Добавление инцидентов в YandexTracker завершено. '
            f'Успешно: {total - error_count} из {total}.'
        )

        return total, error_count
