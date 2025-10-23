import os
from typing import Optional, Union

import telebot
from telebot.types import Message

from .constants import DEBUG_MODE, TG_NOTIFICATIONS_ROTATING_FILE
from .loggers import LoggerFactory
from .utils import Config
from .wraps import retry

tg_manager_config = {
    'TG_TOKEN': os.getenv('TG_TOKEN'),
    'TG_DEFAULT_USER_ID': os.getenv('TG_DEFAULT_USER_ID'),
}
Config.validate_env_variables(tg_manager_config)


class TelegramNotifier:

    logger = LoggerFactory(
        __name__, TG_NOTIFICATIONS_ROTATING_FILE
    ).get_logger()
    max_msg_len = 4096

    def __init__(self, token: str, default_chat_id: str):
        """
        Инициализация Telegram бота

        Args:
            token (str): Токен бота (можно получить у @BotFather)
            default_chat_id (str): ID чата по умолчанию для отправки сообщений
            (можно получить у @userinfobot)
        """
        self.token = token
        self.default_chat_id = default_chat_id
        self.bot = telebot.TeleBot(self.token, parse_mode='Markdown')

    def _format_message(
        self, level: str, message: str, emoji: str = ''
    ) -> str:
        """Форматирование сообщения с уровнем логирования"""
        level_text = level.upper()

        if emoji:
            return f'{emoji} _{level_text}_\n{message}'
        else:
            return f'_{level_text}_\n{message}'

    @retry(logger)
    def _send_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True,
    ) -> Message:
        """
        Отправка текстового сообщения в Telegram

        Args:
            chat_id: ID чата для отправки (если None, используется
            default_chat_id)
            disable_web_page_preview (bool): Отключить предпросмотр ссылок.
            По умолчанию отключено.

        Returns:
            Message: Объект отправленного сообщения
        """
        target_chat_id = chat_id or self.default_chat_id
        valid_text = (
            f'{message[:self.max_msg_len - 3]}...'
        ) if len(message) > self.max_msg_len else message

        return self.bot.send_message(
            chat_id=target_chat_id,
            text=valid_text,
            disable_web_page_preview=disable_web_page_preview,
        )

    def send_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        """
        Отправка сообщений с пропуском ошибок.

        Args:
            chat_id: ID чата для отправки (опционально)
            disable_web_page_preview: Отключить предпросмотр ссылок

        Returns:
            Optional[Message]: Объект сообщения если успешно, иначе None
        """
        try:
            return self._send_message(
                message, chat_id, disable_web_page_preview)
        except Exception as e:
            self.logger.exception(
                f'Не удалось отправить сообщение пользователю {chat_id}:\n{e}')
            return None

    def send_debug_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        if not DEBUG_MODE:
            return
        formatted_message = self._format_message('debug', message, '⚙️')
        return self.send_message(
            formatted_message, chat_id, disable_web_page_preview)

    def send_info_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        formatted_message = self._format_message('info', message, 'ℹ️')
        return self.send_message(
            formatted_message, chat_id, disable_web_page_preview)

    def send_success_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        formatted_message = self._format_message('success', message, '✅')
        return self.send_message(
            formatted_message, chat_id, disable_web_page_preview)

    def send_warning_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        formatted_message = self._format_message('warning', message, '⚠️')
        return self.send_message(
            formatted_message, chat_id, disable_web_page_preview)

    def send_error_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        formatted_message = self._format_message('error', message, '❌')
        return self.send_message(
            formatted_message, chat_id, disable_web_page_preview)

    def send_critical_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        formatted_message = self._format_message('critical', message, '❗️')
        return self.send_message(
            formatted_message, chat_id, disable_web_page_preview)

    def send_custom_message(
        self,
        message: str,
        level: Optional[str] = None,
        emoji: Optional[str] = None,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        """
        Универсальный метод для отправки кастомных сообщений

        Args:
            message: Текст сообщения (с Markdown разметкой)
            level: Уровень логирования (опционально)
            emoji: Emoji для сообщения (опционально)
            chat_id: ID чата для отправки (опционально)
            disable_web_page_preview: Отключить предпросмотр ссылок

        Returns:
            Optional[Message]: Объект сообщения если успешно, иначе None
        """
        if level:
            formatted_message = self._format_message(
                level, message, emoji or '')
        else:
            formatted_message = message  # Просто отправляем как есть

        return self.send_message(
            formatted_message, chat_id, disable_web_page_preview)

    def send_plain_message(
        self,
        message: str,
        chat_id: Optional[Union[str, int]] = None,
        disable_web_page_preview: bool = True
    ) -> Optional[Message]:
        """
        Отправка сообщения без какого-либо форматирования уровня

        Args:
            message: Текст сообщения (с Markdown разметкой)
            chat_id: ID чата для отправки (опционально)
            disable_web_page_preview: Отключить предпросмотр ссылок

        Returns:
            Optional[Message]: Объект сообщения если успешно, иначе None
        """
        return self.send_message(message, chat_id, disable_web_page_preview)

    def send_startup_notification(self, script_name: str):
        message = f'```{script_name}```\nСкрипт запущен ⏰'
        self.send_debug_message(message)

    def send_success_notification(self, script_name: str):
        message = f'```{script_name}```\nСкрипт успешно завершил работу 💡'
        self.send_debug_message(message)

    def send_first_success_notification(self, script_name: str):
        message = (
            f'```{script_name}```\nПервый цикл обработки завершен  🏁')
        self.send_success_message(message)

    def send_warning_counter_notification(
        self, script_name: str, err_count: int, total: int
    ):
        message = (
            f'```{script_name}```\nЕсть ошибки (*{err_count}/{total}*) 📊')
        self.send_warning_message(message)

    def send_error_notification(self, script_name: str, err: Exception):
        message = (
            f'```{script_name}```\nУпал с ошибкой *{type(err).__name__}* 🥊')
        self.send_error_message(message)

    def broadcast_message(
        self,
        message: str,
        chat_ids: list,
        disable_web_page_preview: bool = True
    ) -> dict:
        """
        Отправка сообщения нескольким чатам.

        Args:
            message: Текст сообщения (с Markdown разметкой)
            chat_ids: Список ID чатов для отправки
            disable_web_page_preview: Отключить предпросмотр ссылок

        Returns:
            dict: Результаты отправки по каждому чату
        """
        results = {}
        for chat_id in chat_ids:
            try:
                message_obj = self.send_message(
                    message, chat_id, disable_web_page_preview)
                results[chat_id] = {
                    'success': True,
                    'message_id': (
                        message_obj.message_id) if message_obj else None
                }
            except Exception as e:
                results[chat_id] = {
                    'success': False,
                    'error': str(e)
                }
        return results

    def check_debug_mode(self):
        """Проверяет режим DEBUG и отправляет уведомление в Telegram"""
        if DEBUG_MODE:
            message = (
                'Сервер работает в *отладочном* режиме.\n'
                'Это может представлять угрозу безопасности!'
            )
            tg_manager.send_warning_message(message)
        else:
            message = (
                'Сервер работает в *production* режиме.\n'
                'Безопасность настроена правильно.'
            )
            tg_manager.send_success_message(message)


tg_manager = TelegramNotifier(
    token=tg_manager_config['TG_TOKEN'],
    default_chat_id=tg_manager_config['TG_DEFAULT_USER_ID']
)
