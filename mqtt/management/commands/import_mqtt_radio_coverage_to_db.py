from django.core.management.base import BaseCommand
from pymongo import MongoClient

from mqtt.constants import MQTT_MONGO_DB_URL


class Command(BaseCommand):
    help = 'Импорт данных о радиопокрытии вблизи АМС НБ из MongoDB в БД'

    def handle(self, *args, **options):
        self.check_mongodb_connection()

    def check_mongodb_connection(self):
        client = MongoClient(MQTT_MONGO_DB_URL, serverSelectionTimeoutMS=5000)

        client.admin.command('ping')
        print('Сервер отвечает.')
