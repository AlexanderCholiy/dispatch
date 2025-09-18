import random
from datetime import timedelta
from typing import Optional

from django.db import connection, models
from django.db.models import Count, Min, Q
from django.utils import timezone

from emails.models import EmailFolder, EmailMessage
from users.models import Roles, User
from yandex_tracker.utils import YandexTrackerManager

from .constants import (
    DEFAULT_ERR_STATUS_DESC,
    DEFAULT_ERR_STATUS_NAME,
    DEFAULT_GENERATION_STATUS_DESC,
    DEFAULT_GENERATION_STATUS_NAME,
    DEFAULT_IN_WORK_STATUS_DESC,
    DEFAULT_IN_WORK_STATUS_NAME,
    DEFAULT_NOTIFIED_AVR_STATUS_DESC,
    DEFAULT_NOTIFIED_AVR_STATUS_NAME,
    DEFAULT_NOTIFIED_OP_END_STATUS_DESC,
    DEFAULT_NOTIFIED_OP_END_STATUS_NAME,
    DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_DESC,
    DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME,
    DEFAULT_NOTIFY_AVR_STATUS_DESC,
    DEFAULT_NOTIFY_AVR_STATUS_NAME,
    DEFAULT_NOTIFY_OP_END_STATUS_DESC,
    DEFAULT_NOTIFY_OP_END_STATUS_NAME,
    DEFAULT_NOTIFY_OP_IN_WORK_STATUS_DESC,
    DEFAULT_NOTIFY_OP_IN_WORK_STATUS_NAME,
    DEFAULT_STATUS_DESC,
    DEFAULT_STATUS_NAME,
    DEFAULT_WAIT_ACCEPTANCE_STATUS_DESC,
    DEFAULT_WAIT_ACCEPTANCE_STATUS_NAME,
)
from .models import Incident, IncidentStatus, IncidentStatusHistory
from .validators import IncidentValidator


class IncidentManager(IncidentValidator):

    @staticmethod
    def get_email_thread(email_msg_id: str) -> models.QuerySet[EmailMessage]:
        """Возвращает список связанных сообщений."""
        query = """
        WITH RECURSIVE email_chain AS (
            -- Получаем исходное письмо по email_msg_id
            SELECT
                em.*,
                -- Защита от зацикивания:
                ARRAY[em.email_msg_id::varchar] AS path
            FROM emails_emailmessage AS em
            WHERE email_msg_id = %(email_msg_id)s

            UNION ALL

            -- Рекурсивно ищем письма, которые являются ответами
            SELECT
                em.*,
                ec.path || em.email_msg_id  -- Защита от зацикивания
            FROM emails_emailmessage AS em
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
            FROM emails_emailreference AS er
            JOIN email_chain AS ec
            ON er.email_msg_references IN (
                ec.email_msg_id, ec.email_msg_reply_id
            )
            OR er.email_msg_id = ec.id
        ),
        email_thread_without_email_incident_id AS (
            SELECT id FROM emails_emailmessage
            WHERE id IN (
                SELECT id_1 FROM email_full_chain
                UNION
                SELECT id_2 FROM email_full_chain
            )
            OR email_msg_id = %(email_msg_id)s
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
            SELECT id FROM emails_emailmessage
            WHERE email_incident_id IN (
                SELECT email_incident_id FROM emails_emailmessage
                WHERE id IN (
                    SELECT id FROM email_thread_without_email_incident_id
                )
                AND email_incident_id IS NOT NULL
            )
        )
        SELECT id
        FROM emails_emailmessage
        WHERE id IN (SELECT id FROM email_thread_without_email_incident_id)
        OR id IN (SELECT id FROM email_thread_with_email_incident_id)
        ORDER BY email_date, id DESC;
        """
        params = {'email_msg_id': email_msg_id}

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        ids = [row[0] for row in rows]
        return EmailMessage.objects.filter(id__in=ids).order_by(
            'email_incident_id', 'is_first_email', 'email_date', 'id'
        )

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
        if not email_msg.email_subject:
            return

        yt_incidents_keys = yt_manager.find_yt_number_in_text(
            email_msg.email_subject
        )

        if not yt_incidents_keys:
            return

        incident = (
            Incident.objects.filter(code__in=yt_incidents_keys)
            .order_by('-insert_date')
            .first()
        )
        if incident:
            return incident

        for key in yt_incidents_keys:
            issues = yt_manager.select_issue(key=key)

            for issue in issues:
                database_id = issue.get(yt_manager.database_global_field_id)
                if database_id is not None:
                    try:
                        incident = Incident.objects.get(pk=database_id)
                        return incident
                    except Incident.DoesNotExist:
                        continue

        return

    @staticmethod
    def choice_dispatch_for_incident(
        yt_manager: Optional[YandexTrackerManager],
        max_incident_num_per_user: Optional[int] = None,
        hour_back: int = 12,
    ) -> Optional[User]:
        """
        Возвращает самого свободного диспетчера.

        - выбирает только активных пользователей с ролью DISPATCH;
        - может ограничивать максимальное число активных инцидентов;
        - учитывает нагрузку за последние N часов;
        - выбирает случайно из группы наименее загруженных.
        """
        since_date = timezone.now() - timedelta(hours=hour_back)

        active_users_with_incidents = (
            User.objects
            .filter(is_active=True, role=Roles.DISPATCH)
            .annotate(
                incident_count=Count(
                    'incidents',
                    filter=Q(
                        incidents__is_incident_finish=False,
                        incidents__insert_date__gte=since_date,
                    )
                )
            )
        )

        if max_incident_num_per_user is not None:
            active_users_with_incidents = active_users_with_incidents.filter(
                incident_count__lt=max_incident_num_per_user)

        if yt_manager is not None:
            active_users_with_incidents = active_users_with_incidents.filter(
                username__in=set(yt_manager.real_users_in_yt_tracker.keys())
            )

        if not active_users_with_incidents.exists():
            return None

        # Необходимо выбрать самого свободного диспетчера:
        min_count = active_users_with_incidents.aggregate(
            min_count=Min('incident_count')
        )['min_count']

        free_users = active_users_with_incidents.filter(
            incident_count=min_count
        )

        return random.choice(free_users)

    @staticmethod
    def add_default_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_STATUS_NAME,
            defaults={'description': DEFAULT_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_error_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_ERR_STATUS_NAME,
            defaults={'description': DEFAULT_ERR_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_wait_acceptance_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_WAIT_ACCEPTANCE_STATUS_NAME,
            defaults={'description': DEFAULT_WAIT_ACCEPTANCE_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_generation_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_GENERATION_STATUS_NAME,
            defaults={'description': DEFAULT_GENERATION_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_in_work_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_IN_WORK_STATUS_NAME,
            defaults={'description': DEFAULT_IN_WORK_STATUS_DESC}
        )
        if not incident.statuses.filter(pk=status.pk).exists():
            IncidentStatusHistory.objects.create(
                incident=incident,
                status=status,
                comments=comment
            )
            incident.statuses.add(status)

    @staticmethod
    def add_notify_op_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_NOTIFY_OP_IN_WORK_STATUS_NAME,
            defaults={'description': DEFAULT_NOTIFY_OP_IN_WORK_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notified_op_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_NAME,
            defaults={'description': DEFAULT_NOTIFIED_OP_IN_WORK_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notify_op_end_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_NOTIFY_OP_END_STATUS_NAME,
            defaults={'description': DEFAULT_NOTIFY_OP_END_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notified_op_end_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_NOTIFIED_OP_END_STATUS_NAME,
            defaults={'description': DEFAULT_NOTIFIED_OP_END_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notify_avr_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_NOTIFY_AVR_STATUS_NAME,
            defaults={'description': DEFAULT_NOTIFY_AVR_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notified_avr_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_NOTIFIED_AVR_STATUS_NAME,
            defaults={'description': DEFAULT_NOTIFIED_AVR_STATUS_DESC}
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment
        )
        incident.statuses.add(status)

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

        Особенности:
            - Новое сообщение от noc.rostov@info.t2.ru имеющее в теме
            "(Закрыто)" и для которого найдется письмо с инцидентом будет
            привязано к данному инциденту или по нему не будет создан Новый
            инцидент. В противном случае инцидент по этому письму не будет
            зарегестрирован.

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
        first_email = emails_thread[0] if emails_thread else None
        new_incident = None

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

        # Резервный поиск по коду инцидента в теме письма:
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
                    self.find_pole_and_base_station_in_msg(msg)
                    for msg in emails_thread
                    if (
                        pole := self.find_pole_and_base_station_in_msg(msg)[0]
                    ) is not None
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
        # переписка и первое письмо из стандартной папки INBOX:
        elif (
            actual_email_incident is None
            and is_full_thread
            and first_email.folder == EmailFolder.get_inbox()
        ):
            # Исключение для Tele2:
            # if (
            #     email_msg.email_from == 'noc.rostov@info.t2.ru'
            #     and email_msg.email_subject
            #     and email_msg.email_subject.lower().endswith('(закрыто)')
            # ):
            #     new_incident = False

            #     subject_2_find = email_msg.email_subject.replace(
            #         '(закрыто)', '').strip()

            #     old_email_msg = (
            #         EmailMessage.objects.filter(
            #             email_subject__icontains=subject_2_find,
            #             email_incident__isnull=False
            #         )
            #         .order_by('-email_date')
            #         .first()
            #     )

            #     if old_email_msg:
            #         actual_email_incident = old_email_msg.email_incident

            # else:
            new_incident = True

            actual_email_incident = Incident.objects.create(
                incident_date=emails_thread[0].email_date,
                pole=pole,
                base_station=base_station,
            )

        # У существующей переписки, обновляем номер инцидента к которой она
        # относится:
        if actual_email_incident is not None:
            EmailMessage.objects.filter(id__in=email_ids).update(
                email_incident=actual_email_incident
            )

            # У инцидента обновляем поле с шифром опоры и БС, если там пусто:
            if actual_email_incident.pole is None and pole is not None:
                actual_email_incident.pole = pole
                actual_email_incident.save(update_fields=['pole'])

            if actual_email_incident.base_station is None and (
                base_station is not None
            ):
                actual_email_incident.base_station = base_station
                actual_email_incident.save(update_fields=['base_station'])

            # Выставляем у нового инцидента изначальный статус:
            if new_incident:
                IncidentManager.add_default_status(actual_email_incident)

            return actual_email_incident, new_incident
