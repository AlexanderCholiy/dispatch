from django.db import transaction

from .models import EmailErr


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
