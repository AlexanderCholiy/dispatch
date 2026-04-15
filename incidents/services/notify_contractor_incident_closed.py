from typing import Optional, TypedDict

from django.db import transaction
from django.utils import timezone

from emails.email_parser import email_parser
from emails.models import (
    EmailFolder,
    EmailMessage,
    EmailStatus,
    EmailTo,
    EmailToCC,
)
from emails.services.generate_email_msg_id import generate_message_id
from emails.tasks import send_incident_email_task
from incidents.constants import (
    AVR_CATEGORY,
    RVR_CATEGORY,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_NAME,
)
from incidents.models import Incident
from incidents.services.incident_signature import get_incident_signature


class NotifyContracrorResult(TypedDict):
    notify_avr: bool
    notify_rvr: bool
    msg_id: Optional[int]


def notify_contractor_incident_closed(
    incident: Incident,
    subject: str,
) -> NotifyContracrorResult:
    was_avr = any(
        st.is_avr_category
        and st.status.name in (
            NOTIFIED_CONTRACTOR_STATUS_NAME,
            NOTIFY_CONTRACTOR_STATUS_NAME,
        )
        for st in incident.prefetched_status_history
    )

    was_rvr = any(
        st.is_rvr_category
        and st.status.name in (
            NOTIFIED_CONTRACTOR_STATUS_NAME,
            NOTIFY_CONTRACTOR_STATUS_NAME,
        )
        for st in incident.prefetched_status_history
    )

    avr_emails = set([
        obj.email.email
        for obj in incident.pole.prefetched_pole_avr_emails
    ]) if incident.pole else set()

    avr_emails = set(['alexander.choliy@mail.ru'])

    rvr_emails = set([incident.pole.region.rvr_email.email]) if (
        incident.pole
        and incident.pole.region
        and incident.pole.region.rvr_email
    ) else set()

    rvr_emails = set(['alexander.choliy@outlook.com'])

    if not was_avr or not was_rvr:
        all_msg_addrs = set()
        for em in incident.all_incident_emails:
            to_list: list[EmailTo] = em.prefetched_to
            cc_list: list[EmailToCC] = em.prefetched_cc

            for addr in to_list:
                all_msg_addrs.add(addr.email_to)

            for addr in cc_list:
                all_msg_addrs.add(addr.email_to)

        if avr_emails and avr_emails.intersection(all_msg_addrs):
            was_avr = True
        if rvr_emails and rvr_emails.intersection(all_msg_addrs):
            was_rvr = True

    if not was_avr and was_rvr:
        return {
            'notify_avr': False,
            'notify_rvr': False,
            'msg_id': None,
        }

    email_to = []
    if was_avr:
        for em in avr_emails:
            if em not in email_to and em != email_parser.email_login:
                email_to.append(em)
    if was_rvr:
        for em in rvr_emails:
            if em not in email_to and em != email_parser.email_login:
                email_to.append(em)

    if not email_to:
        return {
            'notify_avr': False,
            'notify_rvr': False,
            'msg_id': None,
        }

    signature = get_incident_signature(incident)

    incident_label = f'{incident.code} ' if incident.code else ''

    email_body = (
        f'Инцидент {incident_label}устранён.'
        '\n\nПри отсутствии возражений со стороны оператора заявка закроется '
        'автоматически через 12 часов.'
        f'{signature}'
    )

    with transaction.atomic():
        now = timezone.now()
        message_id = generate_message_id()

        folder = EmailFolder.objects.get(name='SENT')

        email_msg = EmailMessage.objects.create(
            email_msg_id=message_id,
            email_subject=subject,
            email_from=email_parser.email_login,
            email_date=now,
            email_body=email_body,
            is_first_email=True,
            is_email_from_yandex_tracker=False,
            was_added_2_yandex_tracker=False,
            need_2_add_in_yandex_tracker=True,
            email_incident=incident,
            folder=folder,
            status=EmailStatus.PENDING,
            email_msg_reply_id=None,
        )

        for email in email_to:
            EmailTo.objects.create(
                email_msg=email_msg,
                email_to=email
            )

        transaction.on_commit(
            lambda: send_incident_email_task.delay(email_msg.id)
        )

    return {
        'notify_avr': avr_emails and was_avr,
        'notify_rvr': rvr_emails and was_rvr,
        'msg_id': email_msg.id,
    }
