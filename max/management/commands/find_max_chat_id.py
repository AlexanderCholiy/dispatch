from django.core.management.base import BaseCommand

from core.loggers import max_api_logger
from core.wraps import timer
from max.constants import MAX_CHAT_ID
from max.max_api import max_api


class Command(BaseCommand):
    help = 'Тестирование мессенджера MAX.'

    @timer(max_api_logger)
    def handle(self, *args, **options):
        # last_chat_info = max_api.get_last_update()
        # print(last_chat_info['last_update'])

        # chats_info = max_api.get_chats_info()

        # for chat in chats_info['chats']:
        #     print(chat)

        max_api.send_message(text='Hello world!', chat_id=MAX_CHAT_ID)
