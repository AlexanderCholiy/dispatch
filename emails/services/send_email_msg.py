from django.core.files.base import ContentFile
from django.core.mail import EmailMessage as DjangoEmailMessage, SafeMIMEText
from django.core.mail.backends.smtp import EmailBackend
from email.utils import parsedate_to_datetime
from django.utils import timezone
from django.db import transaction
from datetime import timezone as dt_timezone

from emails.models import EmailMessage, EmailMime, EmailReference


def send_via_django_email(
    email_msg: EmailMessage,
    smtp_user: str,
    smtp_password: str,
    smtp_host: str,
    smtp_port: int = 587,
    use_tls: bool = True,
    use_ssl: bool = False,
) -> None:
    connection = EmailBackend(
        host=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_password,
        use_tls=use_tls,
        use_ssl=use_ssl,
        fail_silently=False,
    )

    # Гарантируем правильный Subject, т.к. некоторые алгоритмы его требуют при
    # ответе:
    subject = email_msg.email_subject or ''
    if email_msg.email_msg_reply_id and not subject.lower().startswith('re:'):
        subject = f'Re: {subject}'

    message = DjangoEmailMessage(
        subject=subject,
        body=email_msg.email_body or '',
        from_email=email_msg.email_from,
        to=[obj.email_to for obj in email_msg.email_msg_to.all()],
        cc=[obj.email_to for obj in email_msg.email_msg_cc.all()],
        connection=connection,
    )

    message.extra_headers['Message-ID'] = email_msg.email_msg_id

    if email_msg.email_msg_reply_id:
        message.extra_headers['In-Reply-To'] = email_msg.email_msg_reply_id

    references = list(
        email_msg.email_references.all()
        .order_by('email_msg__email_date', 'email_msg__id')
        .values_list('email_msg_references', flat=True)
    )
    if email_msg.email_msg_reply_id:
        references = [
            r for r in references if r != email_msg.email_msg_reply_id
        ]
        references.append(email_msg.email_msg_reply_id)

    if references:
        message.extra_headers['References'] = ' '.join(references)

    for attachment in email_msg.email_attachments.all():
        if attachment.file_url:
            message.attach_file(attachment.file_url.path)

    # Бросает исключение, если отправка не удалась:
    message.send(fail_silently=False)
    parsed_date = timezone.now()

    mime_message: SafeMIMEText = message.message()
    raw_mime_bytes = mime_message.as_bytes()

    mime_instance, _ = EmailMime.objects.get_or_create(
        email_msg=email_msg
    )

    safe_msgid = (
        email_msg.email_msg_id
        .strip('<>').replace('/', '_').replace('\\', '_')
    )
    file_name = f'{safe_msgid}.eml'

    mime_instance.file_url.save(
        file_name,
        ContentFile(raw_mime_bytes),
        save=True,
    )

    real_subject = mime_message.get('Subject')

    update_fields = []

    email_msg.email_date = parsed_date
    update_fields.append('email_date')

    if real_subject and email_msg.email_subject != real_subject:
        email_msg.email_subject = real_subject
        update_fields.append('email_subject')

    email_msg.save(update_fields=update_fields)
