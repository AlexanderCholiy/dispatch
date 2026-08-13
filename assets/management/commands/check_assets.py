from django.core.management.base import BaseCommand

from assets.constants import CACHE_KEY_CHECK_ASSETS_RUN, MAX_CHECK_ASSETS_TTL
from assets.services.get_problem_assets_without_incidents import (
    get_problem_assets_without_incidents,
)
from assets.services.make_incident_from_asset import make_incident_from_asset
from core.loggers import assets_logger
from core.wraps import func_timeout, rate_limit_cache, timer
from users.constants import BOT_USERNAME
from users.models import User


class Command(BaseCommand):
    help = 'Проверка активного оборудования в мониторинге.'

    @func_timeout(seconds=MAX_CHECK_ASSETS_TTL)
    @rate_limit_cache(
        assets_logger, CACHE_KEY_CHECK_ASSETS_RUN, MAX_CHECK_ASSETS_TTL
    )
    @timer(assets_logger)
    def handle(self, *args, **options):
        bot_user = User.objects.filter(username=BOT_USERNAME).first()

        unactive_err_assets = get_problem_assets_without_incidents(
            bot_user=bot_user
        )

        if not unactive_err_assets:
            assets_logger.debug(
                'Эскалация по активному оборудованию не требуется.'
            )
            return

        for pole, err_devices in unactive_err_assets.items():
            try:
                make_incident_from_asset(
                    pole=pole, err_devices=err_devices, bot_user=bot_user
                )
            except Exception as e:
                assets_logger.exception(e)
