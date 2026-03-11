from typing import Optional

from notifications.models import Notification, NotificationLevel
from notifications.constants import (
    MAX_NOTIFICATION_TITLE_LEN,
    MAX_NOTIFICATION_TEXT_LEN,
)
from incidents.models import Incident
from users.models import User, Roles
from incidents.services.send_auto_reply import AutoReply


def notify_responsible_user_on_reassign(
    incident: Incident,
    old_user: Optional[User],
    new_user: Optional[User],
    author: Optional[User],
):
    """
    Уведомление при смене ответственного диспетчера.
    - old_user: предыдущий диспетчер
    - new_user: новый диспетчер
    - author: пользователь, который сделал изменение
    """
    """
    Отправка уведомлений при смене ответственного диспетчера.
    - old_user: предыдущий диспетчер
    - new_user: новый диспетчер
    - author: пользователь, который выполнил переназначение
    """
    if old_user == new_user:
        return

    author_name = f'{author.get_full_name()}' if author else 'Система'

    notifications = []

    if old_user:
        title = f'Вы больше не отвечаете за {incident}'
        message = (
            f'Инцидент "{incident}" был переназначен на другого диспетчера.\n'
            f'Автор изменения: {author_name}'
        )
        notifications.append((old_user, title, message, NotificationLevel.LOW))

    if new_user and new_user != old_user:
        title = f'Вам назначен новый инцидент: {incident}'
        message = (
            f'Вы теперь отвечаете за инцидент "{incident}".\n'
            f'Автор назначения: {author_name}'
        )
        notifications.append(
            (new_user, title, message, NotificationLevel.MEDIUM)
        )

    if not notifications:
        targets = User.objects.filter(
            is_active=True, role=Roles.DISPATCH, is_staff=True
        )
        for u in targets:
            title = f'Инцидент без ответственного: {incident}'
            message = (
                f'Инцидент "{incident}" требует назначения ответственного '
                'диспетчера.\n'
                f'Автор изменения: {author_name}'
            )
            notifications.append((u, title, message, NotificationLevel.MEDIUM))

    for user, title, message, level in notifications:
        Notification.objects.create(
            user=user,
            title=AutoReply.truncate_text(title, MAX_NOTIFICATION_TITLE_LEN),
            message=AutoReply.truncate_text(
                message, MAX_NOTIFICATION_TEXT_LEN
            ),
            level=level,
            data={'incident_id': incident.id}
        )
