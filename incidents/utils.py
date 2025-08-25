import os

from django.db import connection, models, transaction
from typing import Optional

from emails.models import EmailMessage
from .models import Incident
from yandex_tracker.utils import YandexTrackerManager
from .validators import IncidentValidator


class IncidentManager(IncidentValidator):

    @staticmethod
    def get_email_thread(
        email_msg_id: str,
        email_table_name: str = 'emails_emailmessage',
        email_reference_table_name: str = 'emails_emailreference',
    ) -> models.QuerySet[EmailMessage]:
        """Возвращает список связанных сообщений."""
        query = f"""
        WITH RECURSIVE email_chain AS (
            -- Получаем исходное письмо по email_msg_id
            SELECT
                em.*,
                -- Защита от зацикивания:
                ARRAY[em.email_msg_id::varchar] AS path
            FROM {email_table_name} AS em
            WHERE email_msg_id = %s

            UNION ALL

            -- Рекурсивно ищем письма, которые являются ответами
            SELECT
                em.*,
                ec.path || em.email_msg_id  -- Защита от зацикивания
            FROM {email_table_name} AS em
            JOIN email_chain AS ec ON em.email_msg_reply_id = ec.email_msg_id
            WHERE NOT em.email_msg_id = ANY(ec.path)  -- Защита от зацикивания
        ),
        email_full_chain AS (
            -- Добавляем письма, которые связаны через email_references
            SELECT
                er.email_msg_id AS id_1,
                ec.id AS id_2,
                er.email_msg_references AS email_msg_id_1,
                ec.email_msg_id AS email_msg_id_2,
                ec.email_msg_reply_id AS email_msg_id_3
            FROM {email_reference_table_name} AS er
            JOIN email_chain AS ec
            ON er.email_msg_references IN (
                ec.email_msg_id, ec.email_msg_reply_id
            )
            OR er.email_msg_id = ec.id
        ),
        email_thread_without_email_incident_id AS (
            SELECT id FROM {email_table_name}
            WHERE id IN (
                SELECT id_1 FROM email_full_chain
                UNION
                SELECT id_2 FROM email_full_chain
            )
            OR email_msg_id = %s
            OR email_msg_id IN (
                SELECT email_msg_id_1 FROM email_full_chain
                UNION
                SELECT email_msg_id_2 FROM email_full_chain
                UNION
                SELECT email_msg_id_3 FROM email_full_chain
            )
            OR email_msg_reply_id IN (
                SELECT email_msg_id_1 FROM email_full_chain
                UNION
                SELECT email_msg_id_2 FROM email_full_chain
                UNION
                SELECT email_msg_id_3 FROM email_full_chain
            )
        ),
        -- Это нужно если мы "вручную связываем письма в цепочку"
        email_thread_with_email_incident_id AS (
            SELECT id FROM {email_table_name}
            WHERE email_incident_id IN (
                SELECT email_incident_id FROM {email_table_name}
                WHERE id IN (
                    SELECT id FROM email_thread_without_email_incident_id
                )
                AND email_incident_id IS NOT NULL
            )
        )
        SELECT id
        FROM {email_table_name}
        WHERE id IN (SELECT id FROM email_thread_without_email_incident_id)
        OR id IN (SELECT id FROM email_thread_with_email_incident_id)
        ORDER BY email_date, id DESC;
        """
        params = [email_msg_id, email_msg_id]

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        ids = [row[0] for row in rows]

        return EmailMessage.objects.filter(id__in=ids)

    @staticmethod
    def get_incident_by_yandex_tracker(
        email_msg: EmailMessage, yt_manager: YandexTrackerManager
    ) -> Optional[Incident]:
        """
        Если письмо было ответом на письмо отправленное из Yandex Tracker,
        тогда связь с основной цепочкой теряется. Поэтому мы из темы письма
        должны проверить есть ли там номер инцидента, и уже по нему
        попробовть вытащить его:
        """
        yt_incidents = yt_manager.find_yt_number_in_text(
            email_msg.email_subject
        )
        actual_email_incident = None
        for key in yt_incidents:
            issues = yt_manager.select_issue(key=key)
            database_ids = [
                id for issue in issues
                if (
                    id := issue.get(yt_manager.database_global_field_id)
                ) is not None
            ]

            for database_id in database_ids:
                try:
                    actual_email_incident = Incident.objects.get(
                        id=database_id)
                    break
                except Incident.DoesNotExist:
                    pass

        return actual_email_incident

    @transaction.atomic()
    def add_incident_from_email(
        self,
        email_msg: EmailMessage,
        yt_manager: Optional[YandexTrackerManager],
    ) -> Optional[tuple[Incident, bool]]:
        """
        Регистрирует инцидент по переписке, связанной с указанным
        сообщением.

        Для предотвращения дублирования инцидентов и возможности восстановления
        всей цепочки переписки, регистрация инцидента производится только в
        том случае, если в переписке присутствует самое первое сообщение.

        Args:
            email_msg (str): EmailMessage, по которому нужно найти переписку.
            yandex_tracker_manager: YandexTrackerManager, для ответов из
            YandexTracker к которым надо восстановить цепочку переписки.

        Returns:
            tuple[Incident, bool] | None
            - Кортеж из Incident, связанного с перепиской и True, если
            инцидент создан впервые, False, если уже существовал.
            - None, если в переписке отсутствует первое сообщение.
        """
        # Все письма относящиеся к переписке:
        emails_thread = self.get_email_thread(email_msg.email_msg_id)

        # Есть ли в переписке первое сообщение:
        is_full_thread = any(et.is_first_email for et in emails_thread)

        email_ids = [email.pk for email in emails_thread]
        actual_email_incident_id: Optional[int] = min(
            (
                email.email_incident.id for email in emails_thread
                if email.email_incident is not None
            ),
            default=None
        )
        actual_email_incident: Optional[Incident] = (
            Incident.objects.get(id=actual_email_incident_id)
        ) if actual_email_incident_id is not None else None

        if not actual_email_incident and yt_manager:
            actual_email_incident = self.get_incident_by_yandex_tracker(
                email_msg, yt_manager)

        # По возможности сразу найдем шифр опоры из всей переписки:
        if (
            not actual_email_incident
            or (actual_email_incident and not actual_email_incident.pole)
        ):
            pole, base_station = next(
                (
                    self.find_pole_in_msg(msg) for msg in emails_thread
                    if (pole := self.find_pole_in_msg(msg)[0]) is not None
                ), (None, None)
            )
        else:
            pole, base_station = (
                actual_email_incident.pole, actual_email_incident.base_station
            )

        # Инцидент по переписке к которой относится письмо существует:
        if actual_email_incident is not None:
            new_incident = False
        # Письмо в переписке не относится ни к одному инциденту, поэтому
        # надо создать новый инцидент, при условии что у нас есть полная
        # переписка:
        elif actual_email_incident is None and is_full_thread:
            random_user = choice_dispatch_for_incident(
                self.yt_client,
                incident_email_config.MAX_INCIDENT_NUM_PER_USER
            )

            new_incident = True
            actual_email_incident = Incident.objects.create(
                incident_date=emails_thread[0].email_date,
                pole=pole,
                base_station=base_station,
                responsible_user=random_user,
            )
