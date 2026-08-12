import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from core.pretty_print import PrettyPrint
from users.models import PendingUser, Roles


class Command(BaseCommand):
    help = 'Создает бота системы, если он не существует'

    BOT_USERNAME = os.getenv('BOT_USERNAME')
    BOT_EMAIL = os.getenv('BOT_EMAIL')
    BOT_PASSWORD = os.getenv('BOT_PASSWORD')

    @transaction.atomic
    def handle(self, *args, **kwargs):

        User = get_user_model()

        missing_vars = []
        if not self.BOT_USERNAME:
            missing_vars.append('BOT_USERNAME')
        if not self.BOT_EMAIL:
            missing_vars.append('BOT_EMAIL')
        if not self.BOT_PASSWORD:
            missing_vars.append('BOT_PASSWORD')

        if missing_vars:
            missing_vars_part = ', '.join(missing_vars)
            msg = (
                ('❌ Не заданы переменные окружения:', False),
                (missing_vars_part, True),
            )
            PrettyPrint.error_print(*msg)
            return

        if User.objects.filter(
            username=self.BOT_USERNAME, is_staff=True
        ).exists():
            msg = (
                ('✅ Бот', False),
                (self.BOT_USERNAME, True),
                ('уже существует.', False),
            )
            PrettyPrint.info_print(*msg)
            return

        pending_deleted, _ = PendingUser.objects.filter(
            Q(username=self.BOT_USERNAME) | Q(email=self.BOT_EMAIL)
        ).delete()
        if pending_deleted:
            msg = (
                ('🧹 Удалены PendingUser с username=', False),
                (self.BOT_USERNAME, True),
                ('или email=', False),
                (self.BOT_EMAIL, True),
            )
            PrettyPrint.warning_print(*msg)

        user_deleted, _ = User.objects.filter(
            Q(username=self.BOT_USERNAME) | Q(email=self.BOT_EMAIL),
        ).exclude(is_superuser=True).delete()
        if user_deleted:
            msg = (
                ('🧹 Удалены обычные пользователи с username=', False),
                (self.BOT_USERNAME, True),
                ('или email=', False),
                (self.BOT_EMAIL, True),
            )
            PrettyPrint.warning_print(*msg)

        User.objects.create_user(
            username=self.BOT_USERNAME,
            email=self.BOT_EMAIL,
            password=self.BOT_PASSWORD,
            role=Roles.USER,
            is_staff=True,
        )

        msg = (
            ('✅ Бот', False),
            (self.BOT_USERNAME, True),
            ('успешно создан.', True)
        )
        PrettyPrint.success_print(*msg)
