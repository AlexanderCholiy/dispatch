from typing import Optional

from django.utils import timezone
from babel.dates import format_datetime

from emails.models import EmailMessage


def get_previous_email_body(prev_email: EmailMessage) -> Optional[str]:
    """
    Формирует блок предыдущего сообщения в стиле Outlook:
    Возвращает None, если блок не нужен.
    """
    if not prev_email.email_body and not prev_email.email_subject:
        return None

    from_value = prev_email.email_from or ''

    to_value = '; '.join(
        obj.email_to
        for obj in prev_email.email_msg_to.all().order_by('email_to')
    )

    cc_value = '; '.join(
        obj.email_to
        for obj in prev_email.email_msg_cc.all().order_by('email_to')
    )

    sent_dt = prev_email.email_date
    if timezone.is_aware(sent_dt):
        sent_dt = timezone.localtime(sent_dt)

    sent_value = format_datetime(
        sent_dt, 'EEE, d MMMM yyyy HH:mm', locale='ru_RU'
    )

    subject_value = prev_email.email_subject or ''

    lines = [
        '',
        '',
        '-----Original Message-----',
        f'From: {from_value}',
        f'Sent: {sent_value}',
        f'To: {to_value}',
    ]

    if cc_value:
        lines.append(f'Cc: {cc_value}')

    lines.append(f'Subject: {subject_value}')
    lines.append('')

    if prev_email.email_body:
        lines.append(prev_email.email_body)

    return '\n'.join(lines)
