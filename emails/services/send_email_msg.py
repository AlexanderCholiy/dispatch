from django.core.files.base import ContentFile
from django.core.mail import EmailMessage as DjangoEmailMessage
from django.core.mail.backends.smtp import EmailBackend

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

    message = DjangoEmailMessage(
        subject=email_msg.email_subject or '',
        body=email_msg.email_body or '',
        from_email=email_msg.email_from,
        to=[obj.email_to for obj in email_msg.email_msg_to.all()],
        cc=[obj.email_to for obj in email_msg.email_msg_cc.all()],
        connection=connection,
    )

    message.extra_headers['Message-ID'] = email_msg.email_msg_id

    if email_msg.email_msg_reply_id:
        message.extra_headers['In-Reply-To'] = email_msg.email_msg_reply_id

    email_msg_references: list[EmailReference] = (
        email_msg.email_references.all()
    )

    references = [ref.email_msg_references for ref in email_msg_references]
    if references:
        message.extra_headers['References'] = ' '.join(references)

    for attachment in email_msg.email_attachments.all():
        if attachment.file_url:
            message.attach_file(attachment.file_url.path)

    # Бросает исключение, если отправка не удалась:
    message.send(fail_silently=False)

    raw_mime_bytes = message.message().as_bytes()

    mime_instance, _ = EmailMime.objects.get_or_create(
        email_msg=email_msg
    )

    file_name = f'{email_msg.id}.eml'

    mime_instance.file_url.save(
        file_name,
        ContentFile(raw_mime_bytes),
        save=True,
    )
