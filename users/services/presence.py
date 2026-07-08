from typing import Optional, TypedDict

from django.core.cache import cache
from django.utils import timezone

from core.services.formatters import format_timedelta_readable, timedelta
from users.constants import PRESENCE_TTL, USERS_CACHE_TTL
from users.models import Roles, User


class UserPresenceStatus(TypedDict):
    is_online: bool
    status_text: str
    last_seen: Optional[float]


class UserPresenceData(TypedDict):
    user_id: int
    user_str: str
    username: str
    avatar_url: Optional[str]
    role_str: str


class UserPresence(TypedDict):
    url: str
    action: str
    timestamp: float


class PresenceService:
    """
    Сервис присутствия.
    Отслеживает онлайн-статус и последнюю страницу пользователя.
    """

    _USER_ONLINE_KEY = 'presence:user:{}'
    _USER_PAGE_KEY = 'presence:user_current_page:{}'
    _PAGE_USERS_KEY = 'presence:page:{}'
    _USER_DATA_KEY = 'presence:user_data:{}'

    @staticmethod
    def update_presence(user: User, page_url: str):
        """Обновляет статус пользователя в Redis."""
        if not user.is_authenticated:
            return

        now_timestamp = timezone.now().timestamp()
        user_id = user.id

        # 1. Помечаем пользователя как ONLINE (TTL очищает оффлайнов):
        cache.set(
            PresenceService._USER_ONLINE_KEY.format(user_id),
            now_timestamp,
            PRESENCE_TTL,
        )

        # 2. Записываем последнюю страницу (только чистый URL):
        normalized_page = page_url.split('?')[0]
        cache.set(
            PresenceService._USER_PAGE_KEY.format(user_id),
            {
                'url': normalized_page,
                'action': f'Просмотр страницы ({normalized_page})',
                'timestamp': now_timestamp,
            },
            PRESENCE_TTL
        )

        # 3. Добавляем ID пользователя в индекс страницы для скорости:
        page_index_key = PresenceService._PAGE_USERS_KEY.format(
            normalized_page
        )

        # Получаем текущий список, добавляем свой ID, убираем дубликаты:
        current_users = cache.get(page_index_key, [])

        unique_users = list(set(current_users + [user_id]))

        cache.set(page_index_key, unique_users, PRESENCE_TTL)

    @staticmethod
    def get_users_on_page(
        page_url: str,
        exclude_user_id: Optional[int] = None
    ) -> list[UserPresenceData]:
        """
        Возвращает список пользователей на странице с их данными.
        Использует кэш для данных профиля, обращаясь к БД только при отсутсвии.
        """
        normalized_page = page_url.split('?')[0]

        allowed_prefixes = [
            '/users/',
            '/schedule/',
            '/planned-work/',
            '/incidents/',
        ]

        is_allowed = False
        for prefix in allowed_prefixes:
            if normalized_page.startswith(prefix):
                is_allowed = True
                break

        if not is_allowed:
            return []

        page_index_key = PresenceService._PAGE_USERS_KEY.format(
            normalized_page
        )

        user_ids = cache.get(page_index_key, [])
        if not user_ids:
            return []

        active_users_data = []

        for uid in user_ids:
            if (
                exclude_user_id and uid == exclude_user_id
                or not cache.get(PresenceService._USER_ONLINE_KEY.format(uid))
            ):
                continue

            cached_user_data = cache.get(
                PresenceService._USER_DATA_KEY.format(uid)
            )

            user_obj = None

            if cached_user_data:
                user_data_dict = cached_user_data
            else:
                try:
                    user_obj = User.objects.get(pk=uid)

                    user_data_dict = {
                        'user_id': user_obj.id,
                        'user_str': str(user_obj),
                        'username': user_obj.username,
                        'avatar_url': user_obj.get_avatar_url,
                        'role_str': Roles(user_obj.role).label,
                    }

                    cache.set(
                        PresenceService._USER_DATA_KEY.format(uid),
                        user_data_dict,
                        USERS_CACHE_TTL,
                    )
                except User.DoesNotExist:
                    continue

            page_info: dict = cache.get(
                PresenceService._USER_PAGE_KEY.format(uid), {}
            )

            active_users_data.append({
                **user_data_dict,
                'page_url': page_info.get('url'),
                'action': page_info.get('action'),
                'last_seen': page_info.get('timestamp')
            })

        active_users_data.sort(key=lambda x: (x['role_str'], x['user_id']))

        return active_users_data

    @staticmethod
    def remove_user(user: User):
        """Полное удаление пользователя из индексов."""
        if not user.is_authenticated:
            return

        cache.delete(PresenceService._USER_ONLINE_KEY.format(user.id))
        cache.delete(PresenceService._USER_PAGE_KEY.format(user.id))

    @staticmethod
    def remove_user_from_page(user: User, page_url: str):
        """
        Удаляет пользователя из индекса конкретной страницы.
        """
        if not user.is_authenticated:
            return

        normalized_page = page_url.split('?')[0]
        page_index_key = PresenceService._PAGE_USERS_KEY.format(
            normalized_page
        )

        current_users = cache.get(page_index_key, [])

        if not current_users:
            return

        updated_users = [uid for uid in current_users if uid != user.id]

        if updated_users:
            cache.set(page_index_key, updated_users, PRESENCE_TTL)
        else:
            cache.delete(page_index_key)

    @staticmethod
    def get_user_status(user: User) -> UserPresenceStatus:
        """
        Возвращает статус для UI.
        """
        if not user:
            return {
                'is_online': False,
                'status_text': 'Давно не появлялся в сети',
                'last_seen': None,
            }

        user_key = PresenceService._USER_ONLINE_KEY.format(user.id)
        last_seen_ts: Optional[float] = cache.get(user_key)

        if last_seen_ts:
            return {
                'is_online': True,
                'status_text': 'Онлайн',
                'last_seen': last_seen_ts,
            }

        if user.last_online:
            diff = timezone.now() - user.last_online
            if diff < timedelta(seconds=PRESENCE_TTL):
                return {
                    'is_online': True,
                    'status_text': 'Онлайн',
                    'last_seen': user.last_online.timestamp()
                }

            formatted_time = format_timedelta_readable(diff)
            return {
                'is_online': False,
                'status_text': f'Был в сети: {formatted_time}',
                'last_seen': user.last_online.timestamp(),
            }

        return {
            'is_online': False,
            'status_text': 'Давно не появлялся в сети',
            'last_seen': None,
        }

    @staticmethod
    def get_user_last_page(user: User) -> Optional[UserPresence]:
        """Получает только последнюю страницу пользователя."""
        if not user.is_authenticated:
            return None

        page_info = cache.get(PresenceService._USER_PAGE_KEY.format(user.id))
        return page_info
