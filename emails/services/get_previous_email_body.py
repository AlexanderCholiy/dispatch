from typing import Optional

from babel.dates import format_datetime
from django.utils import timezone
from django.utils.html import escape

from emails.models import EmailMessage


def get_previous_email_body(
    prev_email: EmailMessage
) -> tuple[Optional[str], Optional[str]]:
    """
    Формирует блок предыдущего сообщения в стиле Outlook.
    Возвращает (plain_text, html_text)
    """

    if not prev_email.email_body and not prev_email.email_subject:
        return None, None

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
        sent_dt,
        'EEE, d MMMM yyyy HH:mm',
        locale='ru_RU'
    )

    subject_value = prev_email.email_subject or ''
    body_value = prev_email.email_body or ''

    plain_lines = [
        '',
        '',
        '-----Original Message-----',
        f'From: {from_value}',
        f'Sent: {sent_value}',
        f'To: {to_value}',
    ]

    if cc_value:
        plain_lines.append(f'Cc: {cc_value}')

    plain_lines.append(f'Subject: {subject_value}')
    plain_lines.append('')
    plain_lines.append(body_value)

    plain_part = '\n'.join(plain_lines)

    escaped_body = escape(body_value).replace('\n', '<br>')

    html_part = f"""
    <div style="margin-top:15px;">
        <div style="
            border-top:1px solid #B5C4DF;
            padding-top:10px;
            font-size:10pt;
        ">
            <b>From:</b> {escape(from_value)}<br>
            <b>Sent:</b> {escape(sent_value)}<br>
            <b>To:</b> {escape(to_value)}<br>
            {"<b>Cc:</b> " + escape(cc_value) + "<br>" if cc_value else ""}
            <b>Subject:</b> {escape(subject_value)}<br>
        </div>

        <blockquote style="
            border-left:2px solid #B5C4DF;
            margin-left:5px;
            padding-left:10px;
            color:#000000;
        ">
            {escaped_body}
        </blockquote>
    </div>
    """

    return plain_part, html_part
