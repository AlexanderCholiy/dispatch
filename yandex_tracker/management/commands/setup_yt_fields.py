from django.core.management.base import BaseCommand

from core.constants import (
    YANDEX_TRACKER_ROTATING_FILE,
)
from core.loggers import LoggerFactory
from yandex_tracker.utils import yt_manager

yt_managment_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_ROTATING_FILE).get_logger


class Command(BaseCommand):
    help = 'Обновление видимости кастомных полей в YandexTracker.'

    def handle(self, *args, **kwargs):
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
