from django.core.management.base import BaseCommand

from core.loggers import max_api_logger
from core.wraps import timer
from max.constants import MAX_CHAT_ID
from max.max_api import max_api


class Command(BaseCommand):
    help = 'Тестирование мессенджера MAX.'

    @timer(max_api_logger)
    def handle(self, *args, **options):
        # chat_id = max_api.get_last_update()['chat_id']
        # chat_id = max_api.get_chats_info()

        max_api.send_message(text='Hello world!', chat_id=MAX_CHAT_ID)
