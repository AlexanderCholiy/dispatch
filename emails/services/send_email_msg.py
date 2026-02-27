from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives, SafeMIMEText
from django.core.mail.backends.smtp import EmailBackend
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.html import escape

from emails.models import EmailMessage, EmailMime, EmailReference

from .get_previous_email_body import get_previous_email_body


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

    # ---------------- Подготовка цитаты ----------------
    plain_body = email_msg.email_body or ''
    html_body_content = (
        escape(email_msg.email_body or '').replace('\n', '<br>')
    )

    reply_to_email = None
    prev_plain = prev_html = ''
    if email_msg.email_msg_reply_id:
        try:
            reply_to_email = EmailMessage.objects.prefetch_related(
                'email_msg_to', 'email_msg_cc',
                Prefetch(
                    'email_references',
                    queryset=EmailReference.objects.order_by(
                        'email_msg__email_date', 'email_msg__id'
                    )
                )
            ).get(email_msg_id=email_msg.email_msg_reply_id)

            prev_plain, prev_html = get_previous_email_body(reply_to_email)
            plain_body += '\n' + prev_plain
            html_body_content = f'{html_body_content}{prev_html}'
        except EmailMessage.DoesNotExist:
            pass

    to_list = [
        obj.email_to
        for obj in getattr(
            email_msg, '_prefetched_email_msg_to', email_msg.email_msg_to.all()
        )
    ]
    cc_list = [
        obj.email_to
        for obj in getattr(
            email_msg, '_prefetched_email_msg_cc', email_msg.email_msg_cc.all()
        )
    ]

    message = EmailMultiAlternatives(
        subject=email_msg.email_subject or '',
        body=plain_body,
        from_email=email_msg.email_from,
        to=to_list,
        cc=cc_list,
        connection=connection,
    )

    message.extra_headers['Message-ID'] = email_msg.email_msg_id

    if email_msg.email_msg_reply_id:
        message.extra_headers['In-Reply-To'] = email_msg.email_msg_reply_id

    references_qs = getattr(
        email_msg,
        '_prefetched_email_references',
        email_msg.email_references.all()
    )
    references = list(
        references_qs.values_list('email_msg_references', flat=True)
    )
    if email_msg.email_msg_reply_id:
        references = [
            r for r in references if r != email_msg.email_msg_reply_id
        ]
        references.append(email_msg.email_msg_reply_id)

    if references:
        message.extra_headers['References'] = ' '.join(references)

    attachments = getattr(
        email_msg,
        '_prefetched_email_attachments',
        email_msg.email_attachments.all()
    )
    intext_attachments = getattr(
        email_msg,
        '_prefetched_email_intext_attachments',
        email_msg.email_intext_attachments.all()
    )

    for attachment in attachments:
        if attachment.file_url:
            message.attach_file(attachment.file_url.path)

    for attachment in intext_attachments:
        if attachment.file_url:
            message.attach_file(attachment.file_url.path)

    message.attach_alternative(html_body_content, 'text/html')

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

    email_msg.email_date = parsed_date
    email_msg.save(update_fields=['email_date'])
