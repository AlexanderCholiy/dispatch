import os
from typing import Optional
from datetime import datetime

from django.db import transaction, models
from core.models import Attachment

from .models import (
    EmailErr,
    EmailMessage,
    EmailReference,
    EmailAttachment,
    EmailInTextAttachment,
    EmailTo,
    EmailToCC,
)


class EmailManager:

    @staticmethod
    @transaction.atomic
    def add_err_msg_bulk(error_ids: list[str]):
        if not error_ids:
            return

        objs_to_create = [
            EmailErr(email_msg_id=msg_id) for msg_id in error_ids
        ]

        EmailErr.objects.bulk_create(objs_to_create, ignore_conflicts=True)

    def add_email_message(
        self,
        email_msg_id: str,
        email_msg_reply_id: Optional[str],
        email_subject: Optional[str],
        email_from: str,
        email_date: datetime,
        email_body: Optional[str],
        is_first_email: bool,
        is_email_from_yandex_tracker: bool,
        was_added_2_yandex_tracker: bool,
        email_to: list[str],
        email_to_cc: list[str],
        email_msg_references: list[str],
        email_attachments_urls: list[str],
        email_attachments_intext_urls: list[str]
    ) -> EmailMessage:
        """Добавление (обновление) сообщения электронной почты в БД."""
        with transaction.atomic():
            email_message, _ = EmailMessage.objects.update_or_create(
                email_msg_id=email_msg_id,
                defaults={
                    'email_msg_reply_id': email_msg_reply_id,
                    'email_subject': email_subject,
                    'email_from': email_from,
                    'email_date': email_date,
                    'email_body': email_body,
                    'is_first_email': is_first_email,
                    'is_email_from_yandex_tracker': (
                        is_email_from_yandex_tracker
                    ),
                    'was_added_2_yandex_tracker': (
                        was_added_2_yandex_tracker
                    ),
                },
            )

            self._update_related_records(
                EmailReference, 'email_msg_references',
                email_message, email_msg_references
            )
            self._update_related_records(
                EmailAttachment, 'file_url',
                email_message, email_attachments_urls
            )
            self._update_related_records(
                EmailInTextAttachment, 'file_url',
                email_message, email_attachments_intext_urls
            )
            self._update_related_records(
                EmailTo, 'email_to',
                email_message, email_to
            )
            self._update_related_records(
                EmailToCC, 'email_to',
                email_message, email_to_cc
            )

        return email_message

    def _update_related_records(
        self,
        model: models.Model,
        field_name: str,
        email_message: EmailMessage,
        values: list[str]
    ):
        if not values:
            return

        existing_values = set(
            model.objects.filter(email_msg=email_message)
            .values_list(field_name, flat=True)
        )
        new_values = set(values) - existing_values

        objs = []
        for value in new_values:
            if issubclass(model, Attachment):
                file_name = os.path.basename(value)
                print(value)
                objs.append(
                    model(
                        email_msg=email_message,
                        file_name=file_name,
                        file_url=value
                    )
                )
            else:
                objs.append(
                    model(email_msg=email_message, **{field_name: value})
                )

        model.objects.bulk_create(objs, ignore_conflicts=True)
