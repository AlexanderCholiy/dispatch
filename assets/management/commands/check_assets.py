from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Проверка активного оборудования в мониторинге.'

    def handle(self, *args, **options):
        ...
