from django.core.management.base import BaseCommand
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import email_logger
from emails.constants import EMAILS_BATCH_SIZE
from emails.models import EmailMessage
from emails.utils import EmailManager


class Command(BaseCommand):
    help = 'Удаляет невалидные MessageID и Message-ReplyID.'

    def handle(self, *args, **options):
        total_count = EmailMessage.objects.count()
        fixed_count = 0
        to_del_count = 0

        bad_ids: list[int] = []

        qs = EmailMessage.objects.all().iterator(
            chunk_size=EMAILS_BATCH_SIZE
        )

        with tqdm(
            total=total_count,
            desc='Валидация EmailMessage',
            colour='cyan',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for ref in qs:
                original_val_1 = ref.email_msg_id
                original_val_2 = ref.email_msg_reply_id

                clean_val_1 = EmailManager.sanitize_email_reference(
                    original_val_1
                )
                clean_val_2 = EmailManager.sanitize_email_reference(
                    original_val_2
                )

                if clean_val_1 is None:
                    # Данные безнадежно битые:
                    to_del_count += 1
                    bad_ids.append(ref.id)

                elif (
                    clean_val_1 != original_val_1
                    or clean_val_2 != original_val_2
                ):
                    # Данные были исправлены:
                    ref.email_msg_id = clean_val_1
                    ref.email_msg_reply_id = clean_val_2
                    ref.save(
                        update_fields=['email_msg_id', 'email_msg_reply_id']
                    )
                    fixed_count += 1

                pbar.update(1)

        if to_del_count or fixed_count:
            email_logger.warning(
                f'Обработано записей EmailMessage: {total_count}. '
                f'Исправлено (нормализовано): {fixed_count}. '
                f'Невосстановимые записи id: {bad_ids}.'
            )
