from typing import Optional

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from assets.constants import (
    CACHE_ASSETS_CANDIDATE_TTL,
    CACHE_KEY_ASSETS_CANDIDATE_PREFIX,
)
from core.loggers import assets_logger
from incidents.models import Comment, Incident
from incidents.services.send_auto_reply import AutoReply
from incidents.utils import IncidentManager
from monitoring.models import DeviceStatus, DeviceType, MSysModem
from notifications.constants import (
    MAX_NOTIFICATION_TEXT_LEN,
    MAX_NOTIFICATION_TITLE_LEN,
)
from notifications.models import Notification, NotificationLevel
from ts.models import Pole
from users.models import Roles, User


def make_incident_from_asset(
    pole: Pole, err_devices: list[MSysModem], bot_user: Optional[User]
) -> Optional[Incident]:
    """
    Создает новый инцидент, если проблема держится долго
    для указанной опоры на основе списка проблемных устройств,
    формирует комментарий с деталями нарушений и рассылает уведомления
    ответственным лицам.
    """
    # Защита от «щелканья» статусов в мониторинге:
    pole_code = str(pole.pole)
    candidate_key = f'{CACHE_KEY_ASSETS_CANDIDATE_PREFIX}{pole_code}'

    candidate_data = cache.get(candidate_key)

    if not candidate_data:
        # --- Сценарий 1: Первый раз видим проблему ---
        # Сохраняем в кэш информацию о времени начала проблемы
        cache.set(
            candidate_key,
            {'start_time': timezone.now().isoformat()},
            timeout=CACHE_ASSETS_CANDIDATE_TTL
        )

        log_msg = (
            f'Кандидат на инцидент: Опора {pole_code}. '
            f'Проблема зафиксирована. '
            f'Ожидание {CACHE_ASSETS_CANDIDATE_TTL // 60} мин'
        )
        assets_logger.debug(log_msg)
        return None

    # --- Сценарий 2: Проблема держится дольше TTL (запись в кэше есть) ---
    # Удаляем запись-кандидат, чтобы следующий цикл мог начать отсчет заново,
    # если проблема исчезнет:
    cache.delete(candidate_key)

    status_groups: list[str] = []

    for eq in err_devices:
        try:
            level_label = DeviceType(eq.level).label
        except ValueError:
            level_label = eq.level

        try:
            status_label = DeviceStatus(eq.status.id).label
        except (ValueError, AttributeError):
            status_label = (
                f'Статус {eq.status.id}'
                if eq.status else 'UNKNOWN'
            )

        status_groups.append(
            f'- {level_label}: {eq.modem_ip.strip()} '
            f'[{status_label}]'
        )

    comment_txt = (
        f'На опоре {pole} с активным оборудованием зафиксированы '
        f'нарушения:\n{"\n".join(status_groups)}'
    )

    with transaction.atomic():
        incident = Incident.objects.create(
            incident_date=timezone.now(),
            pole=pole,
            is_auto_incident=True,
            responsible_user=(
                IncidentManager.choice_dispatch_for_incident(None)
            ),
            is_yt_tracker_controlled=False,
            was_read=False,
        )
        IncidentManager.add_default_status(incident)

        if bot_user:
            Comment.objects.get_or_create(
                incident=incident,
                author=bot_user,
                content=comment_txt,
            )

        author_name = 'Система'

        notifications = []

        responsible_user = incident.responsible_user

        if responsible_user:
            title = (
                f'Вам назначен новый инцидент {incident} '
            )
            message = (
                f'Вы теперь отвечаете за инцидент {incident} '
                'с активным оборудованием.\n'
                f'Автор назначения: {author_name}'
            )
            notifications.append(
                (
                    responsible_user,
                    title,
                    message,
                    NotificationLevel.HIGH,
                )
            )
        else:
            targets = User.objects.filter(
                is_active=True, role=Roles.DISPATCH, is_staff=True
            )
            for u in targets:
                title = (
                    f'Инцидент {incident}  без ответственного.'
                )
                message = (
                    f'Инцидент {incident} '
                    'с активным оборудованием требует назначения '
                    'ответственного диспетчера.\n'
                    f'Автор: {author_name}'
                )
                notifications.append(
                    (u, title, message, NotificationLevel.HIGH)
                )

        for user, title, message, level in notifications:
            Notification.objects.create(
                user=user,
                title=AutoReply.truncate_text(
                    title, MAX_NOTIFICATION_TITLE_LEN
                ),
                message=AutoReply.truncate_text(
                    message, MAX_NOTIFICATION_TEXT_LEN
                ),
                level=level,
                data={'incident_id': incident.id}
            )

    assets_logger.debug(comment_txt.replace('\n', ' '))
