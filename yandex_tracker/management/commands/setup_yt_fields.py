from django.core.management.base import BaseCommand

from core.loggers import yt_logger
from yandex_tracker.utils import yt_manager


class Command(BaseCommand):
    help = 'Обновление видимости кастомных полей в YandexTracker.'

    def handle(self, *args, **kwargs):
        if not yt_manager:
            yt_logger.warning('YandexTrackerManager отсутсвует')
            return

        yt_manager.update_custom_field(
            field_id=yt_manager.database_global_field_id,
            name_en='Local ID',
            name_ru='Local ID',
            description='Идентификатор инцидента в БД',
            readonly=False,
            hidden=False,
            visible=False,
            category_id=yt_manager.agile_category_field_id
        )
        yt_manager.update_custom_field(
            field_id=yt_manager.emails_ids_global_field_id,
            name_en='Local emails IDs',
            name_ru='Local emails IDs',
            description='Идентификаторы писем добавленных по инциденту',
            readonly=False,
            hidden=False,
            visible=False,
            category_id=yt_manager.agile_category_field_id
        )
