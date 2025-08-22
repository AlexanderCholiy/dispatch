from django.db import connection, models
from typing import Optional

from emails.models import EmailMessage
from .models import Incident


class IncidentManager:

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

    def add_incident_from_email(
        self, email_msg: EmailMessage
    ) -> Optional[tuple[Incident, bool]]:
        """
        Регистрирует инцидент по переписке, связанной с указанным
        сообщением.

        Для предотвращения дублирования инцидентов и возможности восстановления
        всей цепочки переписки, регистрация инцидента производится только в
        том случае, если в переписке присутствует самое первое сообщение.

        Args:
            email_msg (str): EmailMessage, по которому нужно найти переписку.

        Returns:
            tuple[Incident, bool] | None
            - Кортеж из Incident, связанного с перепиской и True, если
            инцидент создан впервые, False, если уже существовал.
            - None, если в переписке отсутствует первое сообщение.
        """

        emails_thread = self.get_email_thread(email_msg.email_msg_id)

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
        print(actual_email_incident)
