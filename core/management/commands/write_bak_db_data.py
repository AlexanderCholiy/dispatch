import os
from datetime import datetime
from email.utils import getaddresses
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

from core.loggers import LoggerFactory
from core.pretty_print import PrettyPrint
from core.wraps import timer
from emails.models import EmailMessage, EmailReference, EmailTo, EmailToCC
from incidents.models import Incident

bakup_manager_logger = LoggerFactory(__name__).get_logger


class Command(BaseCommand):
    help = "Чтение данных из внешней базы через сырой SQL"

    external_db_config = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('ADD_POSTGRES_DB'),
        'USER': os.getenv('ADD_POSTGRES_USER'),
        'PASSWORD': os.getenv('ADD_POSTGRES_PASSWORD'),
        'HOST': os.getenv('ADD_DB_HOST'),
        'PORT': int(os.getenv('ADD_DB_PORT', 5432)),
        'TIME_ZONE': settings.TIME_ZONE,
        'ATOMIC_REQUESTS': False,
        'AUTOCOMMIT': True,
        'CONN_MAX_AGE': 0,
        'OPTIONS': {},
        'CONN_HEALTH_CHECKS': True,
    }

    def handle(self, *args, **options):
        self.add_incidents()
        self.add_emails()
        self.add_emails_to()
        self.add_emails_to_cc()
        self.add_emails_references()

    @timer(bakup_manager_logger)
    def add_incidents(self):
        connections.databases['external'] = self.external_db_config
        try:
            with connections['external'].cursor() as cursor:
                cursor.execute('SELECT * FROM incidents_incident;')
                rows = cursor.fetchall()
                total = len(rows)

                for index, row in enumerate(rows):
                    PrettyPrint.progress_bar_debug(
                        index, total, 'Добавление Incident:')

                    pk: int = row[0]
                    insert_date: datetime = row[1]
                    update_date: datetime = row[2]
                    incident_date: datetime = row[3]
                    is_incident_finish: bool = row[4]

                    Incident.objects.update_or_create(
                        pk=pk,
                        defaults={
                            'insert_date': insert_date,
                            'update_date': update_date,
                            'incident_date': incident_date,
                            'is_incident_finish': is_incident_finish,
                        }
                    )

        except OperationalError as e:
            bakup_manager_logger.exception(e)
        finally:
            connections['external'].close()

    @timer(bakup_manager_logger)
    def add_emails(self):
        connections.databases['external'] = self.external_db_config
        try:
            with connections['external'].cursor() as cursor:
                cursor.execute('SELECT * FROM incidents_emailmessage;')
                rows = cursor.fetchall()
                total = len(rows)

                incident_cache = {
                    incident.pk: incident
                    for incident in Incident.objects.all()
                }

                for index, row in enumerate(rows):
                    PrettyPrint.progress_bar_info(
                        index, total, 'Добавление EmailMessage:')

                    pk: int = row[0]
                    email_msg_id: str = row[1]
                    email_msg_reply_id: Optional[str] = row[2]
                    email_subject: Optional[str] = row[3]
                    email_from: str = row[4]
                    email_date: datetime = row[5]
                    email_body: Optional[str] = row[6]
                    email_incident_id: Optional[int] = row[7]
                    is_first_email: bool = row[8]
                    is_email_from_yandex_tracker: Optional[bool] = row[9]

                    if is_email_from_yandex_tracker is None:
                        is_email_from_yandex_tracker = False

                    email_incident = None
                    if email_incident_id:
                        email_incident = incident_cache.get(email_incident_id)

                    EmailMessage.objects.update_or_create(
                        pk=pk,
                        defaults={
                            'email_msg_id': email_msg_id,
                            'email_msg_reply_id': email_msg_reply_id,
                            'email_subject': email_subject,
                            'email_from': email_from,
                            'email_date': email_date,
                            'email_body': email_body,
                            'email_incident': email_incident,
                            'is_first_email': is_first_email,
                            'is_email_from_yandex_tracker': (
                                is_email_from_yandex_tracker),
                            'was_added_2_yandex_tracker': True,
                        }
                    )

        except OperationalError as e:
            bakup_manager_logger.exception(e)
        finally:
            connections['external'].close()

    @timer(bakup_manager_logger)
    def add_emails_to(self):
        connections.databases['external'] = self.external_db_config
        try:
            with connections['external'].cursor() as cursor:
                cursor.execute('SELECT * FROM incidents_emailto;')
                rows = cursor.fetchall()
                total = len(rows)

                email_cache = {
                    email.pk: email
                    for email in EmailMessage.objects.all()
                }

                for index, row in enumerate(rows):
                    PrettyPrint.progress_bar_info(
                        index, total, 'Добавление EmailTo:')

                    email_to: str = row[1]
                    email_msg_id: int = row[2]

                    parsed = getaddresses([email_to])

                    emails = [email for _, email in parsed if email]

                    email_msg = None
                    if email_msg_id:
                        email_msg = email_cache.get(email_msg_id)

                    if not emails or not email_msg:
                        continue

                    for eml in emails:
                        try:
                            EmailTo.objects.get_or_create(
                                email_msg=email_msg,
                                email_to=eml,
                            )
                        except Exception:
                            bakup_manager_logger.warning(
                                email_to, exc_info=True)

        except OperationalError as e:
            bakup_manager_logger.exception(e)
        finally:
            connections['external'].close()

    @timer(bakup_manager_logger)
    def add_emails_to_cc(self):
        connections.databases['external'] = self.external_db_config
        try:
            with connections['external'].cursor() as cursor:
                cursor.execute('SELECT * FROM incidents_emailtocc;')
                rows = cursor.fetchall()
                total = len(rows)

                email_cache = {
                    email.pk: email
                    for email in EmailMessage.objects.all()
                }

                for index, row in enumerate(rows):
                    PrettyPrint.progress_bar_info(
                        index, total, 'Добавление EmailToCc:')

                    email_to: str = row[1]
                    email_msg_id: int = row[2]

                    parsed = getaddresses([email_to])

                    emails = [email for _, email in parsed if email]

                    email_msg = None
                    if email_msg_id:
                        email_msg = email_cache.get(email_msg_id)

                    if not emails or not email_msg:
                        continue

                    for eml in emails:
                        try:
                            EmailToCC.objects.get_or_create(
                                email_msg=email_msg,
                                email_to=eml,
                            )
                        except Exception:
                            bakup_manager_logger.warning(
                                email_to, exc_info=True)

        except OperationalError as e:
            bakup_manager_logger.exception(e)
        finally:
            connections['external'].close()

    @timer(bakup_manager_logger)
    def add_emails_references(self):
        connections.databases['external'] = self.external_db_config
        try:
            with connections['external'].cursor() as cursor:
                cursor.execute('SELECT * FROM incidents_emailreference;')
                rows = cursor.fetchall()
                total = len(rows)

                email_cache = {
                    email.pk: email
                    for email in EmailMessage.objects.all()
                }

                for index, row in enumerate(rows):
                    PrettyPrint.progress_bar_error(
                        index, total, 'Добавление EmailReference:')

                    email_msg_references: str = row[1]
                    email_msg_id: int = row[2]

                    email_msg = None
                    if email_msg_id:
                        email_msg = email_cache.get(email_msg_id)

                    if not email_msg:
                        continue

                    EmailReference.objects.get_or_create(
                        email_msg_references=email_msg_references,
                        email_msg=email_msg,
                    )

        except OperationalError as e:
            bakup_manager_logger.exception(e)
        finally:
            connections['external'].close()
