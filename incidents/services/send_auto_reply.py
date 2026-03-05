from django.db import transaction
from django.utils import timezone

from emails.constants import DISPATCHER_SIGNATURE
from emails.models import (
    EmailFolder,
    EmailMessage,
    EmailReference,
    EmailStatus,
    EmailTo,
    EmailToCC,
)
from emails.services.generate_email_msg_id import generate_message_id
from emails.tasks import send_incident_email_task
from emails.utils import EmailManager
from incidents.constants import (
    AVR_CATEGORY,
    DGU_CATEGORY,
    IN_WORK_STATUS_NAME,
    MAX_EMAILS_ON_CLOSED_INCIDENTS,
    RVR_CATEGORY,
)
from incidents.models import IncidentStatus, IncidentStatusHistory
from yandex_tracker.constants import SEND_AUTO_EMAIL_ON_CLOSED_INCIDENT

from .normalize_incident_subject import normalize_incident_subject


class AutoReply:

    def auto_reply_incident_is_closed(
        self, email: EmailMessage, email_login: str
    ):
        """Отправка автоответа по закрытом инциденту"""
        incident = email.email_incident

        if (
            SEND_AUTO_EMAIL_ON_CLOSED_INCIDENT
            and incident
            and incident.is_incident_finish
            and not incident.is_yt_tracker_controlled
            and email.folder == EmailFolder.get_inbox()
        ):
            now = timezone.now()
            message_id = generate_message_id()

            text_parts = [
                'Добрый день,\n',
                (
                    'Ваше сообщение было отправлено с темой уже закрытого '
                    'инцидента либо является ответом на него.'
                ),
                (
                    'Если у вас есть новая актуальная информация, пожалуйста, '
                    'направьте её отдельным письмом в виде новой заявки.'
                ),
                f'\n\n\n{DISPATCHER_SIGNATURE}'

            ]

            if email.email_subject:
                subject = f'Re: {email.email_subject}'
            elif incident.code:
                subject = f'Re: {incident.code}'
            else:
                subject = 'Re:'

            subject = normalize_incident_subject(subject, incident.code)

            with transaction.atomic():
                folder = EmailFolder.objects.get(name='SENT')

                email_msg = EmailMessage.objects.create(
                    email_msg_id=message_id,
                    email_subject=subject,
                    email_from=email_login,
                    email_date=now,
                    email_body='\n'.join(text_parts),
                    is_first_email=False,
                    is_email_from_yandex_tracker=False,
                    was_added_2_yandex_tracker=False,
                    need_2_add_in_yandex_tracker=False,
                    email_incident=incident,
                    folder=folder,
                    status=EmailStatus.PENDING,
                    email_msg_reply_id=email.email_msg_id,
                )

                # Копируем все references исходного письма:
                for ref in (
                    email.email_references.all()
                    .order_by('email_msg__email_date', 'email_msg__id')
                ):
                    EmailReference.objects.create(
                        email_msg=email_msg,
                        email_msg_references=ref.email_msg_references
                    )

                # Добавляем само письмо, на которое отвечаем:
                EmailReference.objects.create(
                    email_msg=email_msg,
                    email_msg_references=email.email_msg_id
                )

                EmailTo.objects.create(
                    email_msg=email_msg,
                    email_to=email.email_from
                )

                cc_emails = set()

                for to_obj in email.email_msg_to.all():
                    cc_emails.add(to_obj.email_to)

                for cc_obj in email.email_msg_cc.all():
                    cc_emails.add(cc_obj.email_to)

                cc_emails.discard(email.email_from)
                cc_emails.discard(email_login)

                for cc_email in cc_emails:
                    EmailToCC.objects.create(
                        email_msg=email_msg,
                        email_to=cc_email
                    )

                transaction.on_commit(
                    lambda: send_incident_email_task.delay(email_msg.id)
                )

    def open_incident_or_reply(self, email: EmailMessage, email_login: str):
        incident = email.email_incident

        if (
            not incident
            or not incident.is_incident_finish
            or incident.is_yt_tracker_controlled
        ):
            return

        if EmailManager.is_nth_email_after_incident_close(
            incident, MAX_EMAILS_ON_CLOSED_INCIDENTS
        ):
            incident.is_incident_finish = False

            with transaction.atomic():
                new_status, _ = (
                    IncidentStatus.objects
                    .get_or_create(name=IN_WORK_STATUS_NAME)
                )

                comments = (
                    f'Автооткрытие после {MAX_EMAILS_ON_CLOSED_INCIDENTS}-го '
                    'письма после закрытия инцидента'
                )

                category_names = set(
                    incident.categories.values_list('name', flat=True)
                )

                IncidentStatusHistory.objects.create(
                    incident=incident,
                    status=new_status,
                    comments=comments,
                    is_avr_category=AVR_CATEGORY in category_names,
                    is_rvr_category=RVR_CATEGORY in category_names,
                    is_dgu_category=DGU_CATEGORY in category_names,
                )
                incident.statuses.add(new_status)

                incident.save()

            return

        self.auto_reply_incident_is_closed(email, email_login)
