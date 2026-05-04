from django.core.management.base import BaseCommand
from tqdm import tqdm

from core.constants import DEBUG_MODE
from core.loggers import email_logger
from emails.constants import EMAILS_BATCH_SIZE
from emails.models import EmailReference
from emails.utils import EmailManager


class Command(BaseCommand):
    help = 'Удаляет невалидные ссылки на сообщения (References).'

    def handle(self, *args, **options):
        total_count = EmailReference.objects.count()
        fixed_count = 0
        to_del_count = 0

        bad_ids: list[int] = []

        qs = EmailReference.objects.all().iterator(
            chunk_size=EMAILS_BATCH_SIZE
        )

        with tqdm(
            total=total_count,
            desc='Валидация EmailReference',
            colour='cyan',
            position=0,
            leave=True,
            disable=not DEBUG_MODE,
        ) as pbar:
            for ref in qs:
                original_val = ref.email_msg_references

                clean_val = EmailManager.sanitize_email_reference(original_val)

                if clean_val is None:
                    # Данные безнадежно битые:
                    to_del_count += 1
                    bad_ids.append(ref.id)

                elif clean_val != original_val:
                    # Данные были исправлены:
                    ref.email_msg_references = clean_val
                    ref.save(update_fields=['email_msg_references'])
                    fixed_count += 1

                pbar.update(1)

        deleted_count = 0

        for i in range(0, len(bad_ids), EMAILS_BATCH_SIZE):
            chunk_ids = bad_ids[i:i + EMAILS_BATCH_SIZE]
            count, _ = (
                EmailReference.objects.filter(id__in=chunk_ids).delete()
            )
            deleted_count += count

        if to_del_count or fixed_count:
            email_logger.warning(
                f'Обработано записей EmailReference: {total_count}. '
                f'Исправлено (нормализовано): {fixed_count}. '
                'Удалено невосстановимых записей: '
                f'{deleted_count} / {to_del_count}.'
            )
