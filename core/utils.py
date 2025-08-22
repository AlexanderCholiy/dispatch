import os

from django.utils import timezone

from .constants import (
    SUBFOLDER_EMAIL_NAME,
    SUBFOLDER_DATE_FORMAT,
)


def attachment_upload_to(instance, filename: str):
    """
    Формируем путь вида:
    attachments/YYYY-MM-DD/filename.ext
    (относительно MEDIA_ROOT)
    """
    if (
        hasattr(instance, 'email_msg')
        and instance.email_msg
        and instance.email_msg.email_date
    ):
        date_str = instance.email_msg.email_date.strftime(
            SUBFOLDER_DATE_FORMAT
        )
    else:
        date_str = timezone.now().strftime(SUBFOLDER_DATE_FORMAT)

    return os.path.join(SUBFOLDER_EMAIL_NAME, date_str, filename)
