import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from core.pretty_print import PrettyPrint
from core.tg_bot import tg_manager
from users.models import PendingUser


class Command(BaseCommand):
    help = 'Создает дефолтного администратора, если он не существует'

    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

    @transaction.atomic
    def handle(self, *args, **kwargs):

        tg_manager.check_debug_mode(settings.DEBUG)

        User = get_user_model()

        missing_vars = []
        if not self.ADMIN_USERNAME:
            missing_vars.append('ADMIN_USERNAME')
        if not self.ADMIN_EMAIL:
            missing_vars.append('ADMIN_EMAIL')
        if not self.ADMIN_PASSWORD:
            missing_vars.append('ADMIN_PASSWORD')

        if missing_vars:
            missing_vars_part = ', '.join(missing_vars)
            msg = (
                ('❌ Не заданы переменные окружения:', False),
                (missing_vars_part, True),
            )
            PrettyPrint.error_print(*msg)
            return

        if User.objects.filter(
            username=self.ADMIN_USERNAME, is_superuser=True
        ).exists():
            msg = (
                ('✅ Администратор', False),
                (self.ADMIN_USERNAME, True),
                ('уже существует.', False),
            )
            PrettyPrint.info_print(*msg)
            return

        pending_deleted, _ = PendingUser.objects.filter(
            Q(username=self.ADMIN_USERNAME) | Q(email=self.ADMIN_EMAIL)
        ).delete()
        if pending_deleted:
            msg = (
                ('🧹 Удалены PendingUser с username=', False),
                (self.ADMIN_USERNAME, True),
                ('или email=', False),
                (self.ADMIN_EMAIL, True),
            )
            PrettyPrint.warning_print(*msg)

        user_deleted, _ = User.objects.filter(
            Q(username=self.ADMIN_USERNAME) | Q(email=self.ADMIN_EMAIL),
        ).exclude(is_superuser=True).delete()
        if user_deleted:
            msg = (
                ('🧹 Удалены обычные пользователи с username=', False),
                (self.ADMIN_USERNAME, True),
                ('или email=', False),
                (self.ADMIN_EMAIL, True),
            )
            PrettyPrint.warning_print(*msg)

        User.objects.create_user(
            username=self.ADMIN_USERNAME,
            email=self.ADMIN_EMAIL,
            password=self.ADMIN_PASSWORD,
            role='user',
            is_staff=True,
            is_superuser=True,
        )

        msg = (
            ('✅ Администратор', False),
            (self.ADMIN_USERNAME, True),
            ('успешно создан.', True)
        )
        PrettyPrint.success_print(*msg)
