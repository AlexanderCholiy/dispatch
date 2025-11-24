import random
from datetime import datetime, timedelta
from typing import Optional, TypedDict

from django.db import connection, models
from django.db.models import Count, Min, Prefetch, Q, QuerySet
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.constants import INCIDENTS_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from emails.models import EmailFolder, EmailMessage, EmailReference
from users.models import Roles, User
from yandex_tracker.utils import YandexTrackerManager

from .constants import (
    AVR_CATEGORY,
    DEFAULT_STATUS_DESC,
    DEFAULT_STATUS_NAME,
    DGU_CATEGORY,
    ERR_STATUS_DESC,
    ERR_STATUS_NAME,
    GENERATION_STATUS_DESC,
    GENERATION_STATUS_NAME,
    IN_WORK_STATUS_DESC,
    IN_WORK_STATUS_NAME,
    NOTIFIED_CONTRACTOR_STATUS_DESC,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFIED_OP_END_STATUS_DESC,
    NOTIFIED_OP_END_STATUS_NAME,
    NOTIFIED_OP_IN_WORK_STATUS_DESC,
    NOTIFIED_OP_IN_WORK_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_DESC,
    NOTIFY_CONTRACTOR_STATUS_NAME,
    NOTIFY_OP_END_STATUS_DESC,
    NOTIFY_OP_END_STATUS_NAME,
    NOTIFY_OP_IN_WORK_STATUS_DESC,
    NOTIFY_OP_IN_WORK_STATUS_NAME,
    RVR_CATEGORY,
    WAIT_ACCEPTANCE_STATUS_DESC,
    WAIT_ACCEPTANCE_STATUS_NAME,
    END_STATUS_NAME,
    END_STATUS_DESC,
)
from .models import (
    Incident,
    IncidentCategory,
    IncidentStatus,
    IncidentStatusHistory,
)
from .validators import IncidentValidator

incident_manager_logger = LoggerFactory(
    __name__, INCIDENTS_LOG_ROTATING_FILE
).get_logger()


class EmailNode(TypedDict):
    email: EmailMessage  # объект письма
    children: list['EmailNode']  # ответы на это письмо
    branch_ids: list[int]  # плоский список ID всех писем в этой ветке
    min_date: Optional[datetime]
    max_date: Optional[datetime]


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
            'email_incident_id', 'email_date', '-is_first_email', 'id'
        )

    @staticmethod
    def get_incident_by_yandex_tracker(
        email_msg: EmailMessage, yt_manager: YandexTrackerManager
    ) -> Optional[Incident]:
        """
        Получаем локальный Incident по письму из YandexTracker.

        Логика:
        1. Ищем номер инцидента в теме письма.
        2. Проверяем, есть ли локальный Incident по коду.
        3. Если нет, проверяем database_id в YT issue.
        4. Если database_id нет, но задача с этим кодом есть в трекере —
        создаем инцидент вручную по первому коду из темы письма.
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

        found_issues = []

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
                else:
                    found_issues.append(issue)

        # Если есть хотя бы одна задача без database_id, создаём локальный
        # инцидент по первой такой задаче:
        if found_issues:
            return yt_manager.create_incident_from_issue(
                found_issues[0], False)

        return

    @staticmethod
    def choice_dispatch_for_incident(
        yt_manager: Optional[YandexTrackerManager],
        max_incident_num_per_user: Optional[int] = None,
        hour_back: int = 3,
    ) -> Optional[User]:
        """
        Возвращает самого свободного диспетчера, который сейчас работает.

        - выбирает только активных пользователей с ролью DISPATCH;
        - может ограничивать максимальное число активных инцидентов;
        - учитывает нагрузку за последние N часов;
        - выбирает случайно из группы наименее загруженных.
        """
        since_date = timezone.now() - timedelta(hours=hour_back)

        active_users = User.objects.filter(is_active=True, role=Roles.DISPATCH)

        working_users = [
            u.pk for u in active_users
            if hasattr(u, 'work_schedule') and u.work_schedule.is_working_now
        ]
        if not working_users:
            return

        qs = active_users.filter(pk__in=working_users)

        active_users_with_incidents = qs.annotate(
            incident_count=Coalesce(
                Count(
                    'incidents',
                    filter=Q(
                        incidents__is_incident_finish=False,
                        incidents__insert_date__gte=since_date,
                    )
                ),
                0
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
            return

        # Необходимо выбрать самого свободного диспетчера:
        min_count = active_users_with_incidents.aggregate(
            min_count=Min('incident_count')
        )['min_count']

        free_users = active_users_with_incidents.filter(
            incident_count=min_count
        )

        if not free_users:
            return

        return random.choice(free_users)

    @staticmethod
    def add_default_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=DEFAULT_STATUS_NAME,
            defaults={'description': DEFAULT_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_error_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=ERR_STATUS_NAME,
            defaults={'description': ERR_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_wait_acceptance_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=WAIT_ACCEPTANCE_STATUS_NAME,
            defaults={'description': WAIT_ACCEPTANCE_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_generation_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=GENERATION_STATUS_NAME,
            defaults={'description': GENERATION_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_end_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=END_STATUS_NAME,
            defaults={'description': END_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_in_work_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=IN_WORK_STATUS_NAME,
            defaults={'description': IN_WORK_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notify_op_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=NOTIFY_OP_IN_WORK_STATUS_NAME,
            defaults={'description': NOTIFY_OP_IN_WORK_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notified_op_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=NOTIFIED_OP_IN_WORK_STATUS_NAME,
            defaults={'description': NOTIFIED_OP_IN_WORK_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notify_op_end_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=NOTIFY_OP_END_STATUS_NAME,
            defaults={'description': NOTIFY_OP_END_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notified_op_end_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=NOTIFIED_OP_END_STATUS_NAME,
            defaults={'description': NOTIFIED_OP_END_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notify_contractor_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=NOTIFY_CONTRACTOR_STATUS_NAME,
            defaults={'description': NOTIFY_CONTRACTOR_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
        )
        incident.statuses.add(status)

    @staticmethod
    def add_notified_contractor_status(
        incident: Incident, comment: Optional[str] = None
    ) -> None:
        status, _ = IncidentStatus.objects.get_or_create(
            name=NOTIFIED_CONTRACTOR_STATUS_NAME,
            defaults={'description': NOTIFIED_CONTRACTOR_STATUS_DESC}
        )
        category_names = set(
            incident.categories.all().values_list('name', flat=True)
        )
        IncidentStatusHistory.objects.create(
            incident=incident,
            status=status,
            comments=comment,
            is_avr_category=AVR_CATEGORY in category_names,
            is_rvr_category=RVR_CATEGORY in category_names,
            is_dgu_category=DGU_CATEGORY in category_names,
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

        ОТКЛЮЧЕНО, т.к. скрипт всё равно работает непрерывно в одном потоке,
        а функция определения первого письма была изменена:
        Для предотвращения дублирования инцидентов и возможности восстановления
        всей цепочки переписки, регистрация инцидента производится только в
        том случае, если в переписке присутствует самое первое сообщение.

        Особенности:
            - Новое сообщение от noc.rostov@info.t2.ru имеющее в теме
            "(Закрыто)" и для которого найдется письмо с инцидентом будет
            привязано к данному инциденту или по нему не будет создан Новый
            инцидент. В противном случае инцидент по этому письму не будет
            зарегестрирован.
            - Если у нас уже есть письма с таким же отправителем, темой и
            телом, и среди них есть связанные инциденты, которые ещё не
            завершены, то при поступлении нового письма находим первый (
            старейший) и привязываем новое письмо к нему. У такого письма
            отмечаем was_added_2_yandex_tracker = True чтобы не дублировать
            его в трекере.

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

        # Есть ли в переписке первое сообщение (отключено):
        # is_full_thread = any(et.is_first_email for et in emails_thread)

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

        # Исключение для писем с одинаковой темой, телом и отправителем:
        if not actual_email_incident:
            similar_messages_qs = (
                EmailMessage.objects.filter(
                    email_subject=email_msg.email_subject,
                    email_body=email_msg.email_body,
                    email_from=email_msg.email_from,
                    was_added_2_yandex_tracker=True,
                    email_incident__isnull=False,
                    email_incident__is_incident_finish=False,
                )
                .select_related('email_incident')
                .order_by('email_date')
            )
            if similar_messages_qs.exists():
                actual_email_incident = (
                    similar_messages_qs.first().email_incident
                )
                email_msg.was_added_2_yandex_tracker = True
                email_msg.save()

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
            # and is_full_thread
            and first_email.folder == EmailFolder.get_inbox()
        ):
            # Исключение для Tele2:
            if (
                email_msg.email_from == 'noc.rostov@info.t2.ru'
                and email_msg.email_subject
                and email_msg.email_subject.lower().endswith('(закрыто)')
            ):
                subject_2_find = email_msg.email_subject.lower().replace(
                    '(закрыто)', ''
                ).strip()

                old_email_msg = (
                    EmailMessage.objects.filter(
                        email_from='noc.rostov@info.t2.ru',
                        email_subject__istartswith=subject_2_find,
                        email_incident__isnull=False,
                        email_incident__is_incident_finish=False,
                    )
                    .order_by('-email_date')
                    .first()
                )

                if old_email_msg:
                    new_incident = False
                    actual_email_incident = old_email_msg.email_incident

            if actual_email_incident is None:
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

    @staticmethod
    def all_incident_emails(incident: Incident) -> set[str]:
        """Собираем все email, фигурирующие в письмах по инциденту."""
        incident_emails = set()

        # FROM
        incident_emails.update(
            em.email_from for em in incident.email_messages.all()
        )

        # TO
        incident_emails.update(
            eto.email_to
            for em in incident.email_messages.all()
            for eto in em.email_msg_to.all()
        )

        # CC
        incident_emails.update(
            ecc.email_to
            for em in incident.email_messages.all()
            for ecc in em.email_msg_cc.all()
        )

        return incident_emails

    @staticmethod
    def get_avr_emails(incident: Incident) -> list[str]:
        email_to = []
        if (
            incident.pole
            and incident.pole.avr_contractor
        ):
            pole_emails = incident.pole.pole_emails.filter(
                contractor=incident.pole.avr_contractor
            ).select_related('email')

            for pole_email in pole_emails:
                if pole_email.email:
                    email_to.append(pole_email.email.email)

        return email_to

    @staticmethod
    def get_rvr_emails(incident: Incident) -> list[str]:
        email_to = []
        if (
            incident.pole
            and incident.pole.region
            and incident.pole.region.rvr_email
        ):
            email_to.append(incident.pole.region.rvr_email.email)

        return email_to

    @staticmethod
    def get_last_status_by_name(
        incident: Incident,
        name: str,
        is_avr_category: Optional[bool] = None,
        is_rvr_category: Optional[bool] = None,
        is_dgu_category: Optional[bool] = None,
    ) -> Optional[IncidentStatusHistory]:
        """
        Возвращает последнее вхождение определенного статуса по его названию
        для данного инцидента или None, если такого статуса не было.
        """
        queryset = IncidentStatusHistory.objects.filter(
            incident=incident,
            status__name=name
        )

        if is_avr_category is not None:
            queryset = queryset.filter(is_avr_category=is_avr_category)

        if is_rvr_category is not None:
            queryset = queryset.filter(is_rvr_category=is_rvr_category)

        if is_dgu_category is not None:
            queryset = queryset.filter(is_dgu_category=is_dgu_category)

        return queryset.order_by('-insert_date').first()

    @staticmethod
    def auto_update_avr_rvr_dates(incident: Incident) -> bool:
        """
        Автоматически обновляет даты начала и окончания АВР и РВР.
        Метод save НЕ вызывается.
        """
        updated = False

        category_names: set[IncidentCategory] = {
            c.name for c in incident.categories.all()
        }

        if not hasattr(incident, 'prefetched_statuses'):
            relevant_statuses = list(
                IncidentStatusHistory.objects.filter(
                    (
                        models.Q(is_avr_category=True)
                        | models.Q(is_rvr_category=True)
                    ),
                    incident=incident,
                    status__name__in=[
                        NOTIFIED_CONTRACTOR_STATUS_NAME,
                        NOTIFIED_OP_END_STATUS_NAME,
                    ],
                )
                .select_related('status').order_by('-insert_date')
            )
        else:
            relevant_statuses: list[IncidentStatusHistory] = [
                s for s in incident.prefetched_statuses
                if (
                    (s.is_avr_category or s.is_rvr_category)
                    and s.status.name in [
                        NOTIFIED_CONTRACTOR_STATUS_NAME,
                        NOTIFIED_OP_END_STATUS_NAME,
                    ],
                )
            ]

        last_statuses = {
            'avr_start': None,
            'avr_end': None,
            'rvr_start': None,
            'rvr_end': None,
        }

        # Перебираем статусы (в порядке убывания даты) и заполняем словарь
        # первыми (последними) встреченными:
        for status in relevant_statuses:
            if status.status.name == NOTIFIED_CONTRACTOR_STATUS_NAME:
                if (
                    status.is_avr_category
                    and last_statuses['avr_start'] is None
                ):
                    last_statuses['avr_start'] = status
                elif (
                    status.is_rvr_category
                    and last_statuses['rvr_start'] is None
                ):
                    last_statuses['rvr_start'] = status
            elif status.status.name == NOTIFIED_OP_END_STATUS_NAME:
                if (
                    status.is_avr_category
                    and last_statuses['avr_end'] is None
                ):
                    last_statuses['avr_end'] = status
                elif (
                    status.is_rvr_category
                    and last_statuses['rvr_end'] is None
                ):
                    last_statuses['rvr_end'] = status

        last_notified_avr_start_status = last_statuses['avr_start']
        last_notified_avr_end_status = last_statuses['avr_end']
        last_notified_rvr_start_status = last_statuses['rvr_start']
        last_notified_rvr_end_status = last_statuses['rvr_end']

        # Обновляем дату начала принятия работ подрядчиком:
        if (
            AVR_CATEGORY in category_names
            and not incident.avr_start_date
            and last_notified_avr_start_status
            and (
                not last_notified_avr_end_status
                or last_notified_avr_start_status.insert_date
                <= last_notified_avr_end_status.insert_date
            )
        ):
            incident.avr_start_date = (
                last_notified_avr_start_status.insert_date
            )
            updated = True

        if (
            RVR_CATEGORY in category_names
            and not incident.rvr_start_date
            and last_notified_rvr_start_status
            and (
                not last_notified_rvr_end_status
                or last_notified_rvr_start_status.insert_date
                <= last_notified_rvr_end_status.insert_date
            )
        ):
            incident.rvr_start_date = (
                last_notified_rvr_start_status.insert_date
            )
            updated = True

        # Обновляем дату завершения работ подрядчика:
        if (
            not incident.avr_end_date
            and incident.avr_start_date
            and AVR_CATEGORY in category_names
            and (
                (
                    last_notified_avr_end_status
                    and (
                        last_notified_avr_end_status.insert_date
                        >= incident.avr_start_date
                    )
                )
                or (
                    incident.incident_finish_date
                    and (
                        incident.incident_finish_date
                        >= incident.avr_start_date
                    )
                )
            )
        ):
            incident.avr_end_date = (
                last_notified_avr_end_status.insert_date
            ) if last_notified_avr_end_status else (
                incident.incident_finish_date
            )
            updated = True

        if (
            not incident.rvr_end_date
            and incident.rvr_start_date
            and RVR_CATEGORY in category_names
            and (
                (
                    last_notified_rvr_end_status
                    and (
                        last_notified_rvr_end_status.insert_date
                        >= incident.rvr_start_date
                    )
                )
                or (
                    incident.incident_finish_date
                    and (
                        incident.incident_finish_date
                        >= incident.rvr_start_date
                    )
                )
            )
        ):
            incident.rvr_end_date = (
                last_notified_rvr_end_status.insert_date
            ) if last_notified_rvr_end_status else (
                incident.incident_finish_date
            )
            updated = True

        return updated

    def build_email_tree(
        self, emails: QuerySet[EmailMessage], sort_reverse: bool = False
    ) -> list[EmailNode]:
        """
        Строит дерево email-цепочки.
        Использует reply_id и references.
        """
        msg_groups: list[set[EmailMessage]] = []
        emails_set = set(emails)

        # 1. Формируем группы связанных писем:
        for email in emails_set:
            all_ids: set[str] = {email.email_msg_id, }

            if email.email_msg_reply_id:
                all_ids.add(email.email_msg_reply_id)

            if hasattr(email, 'prefetched_references'):
                references: list[EmailReference] = email.prefetched_references
            else:
                references: list[EmailReference] = list(
                    email.email_references.select_related('email_msg')
                )

            ref_ids: set[str] = {
                ref.email_msg_references
                for ref in references if ref.email_msg_references
            }
            all_ids.update(ref_ids)

            # Находим пересекающиеся письма:
            overlapping_emails = {
                em for em in emails_set
                if (
                    em.email_msg_id in all_ids
                    or (
                        em.email_msg_reply_id
                        and em.email_msg_reply_id in all_ids
                    )
                )
            }

            # Проверяем, есть ли эти письма уже в какой-то существующей группе:
            existing_groups = [g for g in msg_groups if g & overlapping_emails]

            if existing_groups:
                # Объединяем все пересекающиеся группы + новые письма:
                merged_group = set().union(
                    *existing_groups, overlapping_emails
                )
                # Удаляем старые группы:
                msg_groups = [
                    g for g in msg_groups if g not in existing_groups
                ]
                msg_groups.append(merged_group)
            else:
                msg_groups.append(overlapping_emails)

        # 2. Строим EmailNode для каждой группы
        result: list[EmailNode] = []

        def group_sort_key(g: set[EmailMessage]):
            dates = [e.email_date for e in g]
            ids = [e.id for e in g]

            if not sort_reverse:
                return (
                    min(dates),
                    min(ids),
                )
            else:
                return (
                    max(dates),
                    max(ids),
                )

        msg_groups = sorted(
            msg_groups,
            key=group_sort_key,
            reverse=sort_reverse,
        )

        for group in msg_groups:
            # Сортируем письма по дате
            sorted_group = sorted(
                group,
                key=lambda e: (e.email_date, e.id),
                reverse=sort_reverse,
            )
            branch_ids = [e.id for e in sorted_group]

            root_email = sorted_group[0]
            children_emails = sorted_group[1:]

            msg_id_map = {e.email_msg_id: e for e in sorted_group}

            children_nodes = []
            for child_email in children_emails:
                child_branch_ids = []

                reply_id = child_email.email_msg_reply_id

                while reply_id and reply_id in msg_id_map:
                    parent_email = msg_id_map[reply_id]

                    if parent_email.id not in child_branch_ids:
                        child_branch_ids.append(parent_email.id)

                    reply_id = parent_email.email_msg_reply_id

                    if len(child_branch_ids) > 100:
                        incident_manager_logger.critical(
                            'Слишком длинная ветка email. '
                            f'ID текущего письма: {child_email.id}'
                        )
                        break

                child_branch_ids.sort()

                children_nodes.append(
                    EmailNode(
                        email=child_email,
                        branch_ids=child_branch_ids,
                        children=[],
                        min_date=None,
                        max_date=None,
                    )
                )

            branch_ids.sort()

            if sort_reverse:
                min_date = sorted_group[-1].email_date
                max_date = sorted_group[0].email_date
            else:
                min_date = sorted_group[0].email_date
                max_date = sorted_group[-1].email_date

            root_node = EmailNode(
                email=root_email,
                branch_ids=branch_ids,
                children=children_nodes,
                min_date=min_date,
                max_date=max_date,
            )

            result.append(root_node)

        return result

    def prepare_incident_info(self, incident_id: int) -> Optional[Incident]:
        """
        Запрос для подготовки информации об инциденте со всей перепиской.
        """
        incident = (
            Incident.objects
            .select_related(
                'incident_type',
                'responsible_user',
                'pole',
                'pole__region',
                'base_station',
            )
            .prefetch_related(
                'history',
                'base_station__operator',
                'categories',
                Prefetch(
                    'status_history',
                    queryset=IncidentStatusHistory.objects.select_related(
                        'status__status_type'
                    ).order_by('-insert_date'),
                    to_attr='prefetched_status_history'
                ),
                Prefetch(
                    'email_messages',
                    queryset=EmailMessage.objects.select_related(
                        'folder', 'email_mime'
                    )
                    .prefetch_related(
                        Prefetch(
                            'email_references',
                            queryset=EmailReference.objects.select_related(
                                'email_msg'
                            ).order_by('id'),
                            to_attr='prefetched_references'
                        ),
                        'email_attachments',
                        'email_intext_attachments',
                        'email_msg_to',
                        'email_msg_cc',
                    ).order_by('-email_date', 'is_first_email'),
                    to_attr='all_incident_emails'
                ),
            )
            .filter(pk=incident_id)
            .first()
        )

        if not incident:
            return

        if getattr(incident, 'prefetched_status_history', None):
            latest_status = incident.prefetched_status_history[0]
            incident.latest_status_name = latest_status.status.name
            incident.latest_status_date = latest_status.insert_date
            incident.latest_status_class = (
                latest_status.status.status_type.css_class
            )
        else:
            incident.latest_status_name = None
            incident.latest_status_date = None
            incident.latest_status_class = None

        return incident
