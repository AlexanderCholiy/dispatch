import json
from typing import Any, Optional

from django.core.management.base import BaseCommand
from paho.mqtt.client import Client, MQTTMessage
from sshtunnel import SSHTunnelForwarder

from core.loggers import monitoring_paas_logger
from core.wraps import timer
from monitoring.constants import (
    MQTT_PAAS_HOST,
    MQTT_PAAS_PORT,
    MQTT_PAAS_PSWD,
    MQTT_PAAS_TOPIC,
    MQTT_PAAS_USER,
)


class Command(BaseCommand):
    help = 'Регистрация инцидентов на объектах PaaS (через SSH туннель)'

    client = Client()
    tunnel = SSHTunnelForwarder(
        ssh_address_or_host=(MQTT_PAAS_HOST, 22),
        ssh_username=MQTT_PAAS_USER,
        ssh_password=MQTT_PAAS_PSWD,
        remote_bind_address=(MQTT_PAAS_HOST, MQTT_PAAS_PORT),
        local_bind_address=('127.0.0.1', 0),
    )

    @timer(monitoring_paas_logger)
    def handle(self, *args, **kwargs):

        try:
            self.tunnel.start()

            local_port = self.tunnel.local_bind_port

            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message

            self.client.username_pw_set(MQTT_PAAS_USER, MQTT_PAAS_PSWD)
            self.client.connect('127.0.0.1', local_port)
            self.client.loop_forever()
        except KeyboardInterrupt:
            self.client.disconnect()
            self.tunnel.stop()
        except Exception as e:
            monitoring_paas_logger.exception(f'Критическая ошибка сети: {e}')
            self.tunnel.stop()

    def _on_connect(
        self,
        client: Client,
        userdata: Optional[Any],
        flags: dict[str, Any],
        rc: int
    ):
        """
        Callback-функция, вызываемая автоматически при попытке подключения к
        брокеру.

        Args:
            client: Экземпляр MQTT-клиента.
            userdata: Данные, переданные при создании клиента.
            flags: Флаги ответа от сервера.
            rc: Код возврата. Ноль означает успех.
        """
        if rc == 0:
            result, _ = client.subscribe(MQTT_PAAS_TOPIC)
            monitoring_paas_logger.debug(
                f'Успешно подключено и подписано на топик: {MQTT_PAAS_TOPIC} '
                f'(Result: {result})'
            )
        else:
            monitoring_paas_logger.error(f'Ошибка подключения: код {rc}')

    def _on_message(
        self,
        client: Client,
        userdata: Optional[Any],
        msg: MQTTMessage
    ):
        """
        Callback-функция, вызываемая автоматически при получении сообщения из
        топика.

        Args:
            client: Экземпляр MQTT-клиента.
            userdata: Данные пользователя.
            msg: Объект сообщения MQTT, содержащий topic, payload и qos.
        """
        payload_str = msg.payload.decode('utf-8')

        try:
            data = json.loads(payload_str)
            print(data)
        except json.JSONDecodeError:
            monitoring_paas_logger.error(
                f'Ошибка парсинга JSON: {payload_str}'
            )
        except Exception as e:
            monitoring_paas_logger.exception(
                f'Неожиданная ошибка обработки данных: {e}'
            )
