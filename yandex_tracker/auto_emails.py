from typing import Optional

from core.constants import YANDEX_TRACKER_AUTO_EMAILS_ROTATING_FILE
from core.loggers import LoggerFactory
from emails.email_parser import EmailParser
from emails.models import EmailMessage
from incidents.constants import DEFAULT_ERR_STATUS_NAME
from incidents.models import Incident
from incidents.utils import IncidentManager

from .constants import CURRENT_TZ, MAX_PREVIEW_TEXT_LEN
from .utils import YandexTrackerManager

auto_yt_emails_logger = LoggerFactory(
    __name__, YANDEX_TRACKER_AUTO_EMAILS_ROTATING_FILE).get_logger


class AutoEmailsFromYT:

    def __init__(
        self,
        yt_manager: YandexTrackerManager,
        email_parser: EmailParser,
    ):
        self.yt_manager = yt_manager
        self.email_parser = email_parser

    def send_auto_reply(
        self,
        issue: dict,
        incident: Incident,
        email_to: list[str],
        success_status_key: str,
        success_message: str,
        text_template: str,
        email_to_cc: Optional[list[str]] = None,
        subject_template: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Универсальная функция для отправки автоответов.
        Так как YandexTracker не предоставляет данные об отправленных email,
        в копию добавляем email по которому создаются автоматические заявки
        в YandexTracker.

        Args:
            issue: Данные заявки из Yandex Tracker
            incident: Объект инцидента
            email_to: список получателей
            success_status_key: Ключ статуса при успешной отправке
            success_message: Сообщение для статуса при успехе
            email_sender_func: Функция отправки email
            text_template: Шаблон текста письма

        Kwargs:
            notify_before_message: Сообщение для обновления статуса инцидента
            subject_template: Шаблон темы письма
            error_message: Сообщение об ошибке
            email_to_cc: Получатели в копии

        Returns:
            bool: Успешность отправки
        """
        issue_key = issue['key']
        error_message = error_message or (
            'Не удалось отправить автоматический ответ')

        email_to_cc = email_to_cc if email_to_cc else []

        if (
            self.email_parser.email_login not in email_to_cc
            and self.email_parser.email_login not in email_to
        ):
            email_to_cc.append(self.email_parser.email_login)

        success_sent_email = self._send_email(
            issue, email_to, email_to_cc, text_template, subject_template)

        if success_sent_email:
            self.yt_manager.update_issue_status(
                issue_key, success_status_key, success_message
            )
            return True
        else:
            self._handle_error(issue_key, incident, error_message)
            return False

    def _handle_error(
        self,
        issue_key: str,
        incident: Incident,
        error_message: str,
    ) -> None:
        """Обрабатывает ошибку отправки."""
        was_status_update = self.yt_manager.update_issue_status(
            issue_key, self.yt_manager.error_status_key, error_message
        )
        if was_status_update:
            auto_yt_emails_logger.debug(error_message)
            IncidentManager.add_error_status(incident, error_message)

    def _send_email(
        self,
        issue: dict,
        email_to: list[str],
        email_to_cc: Optional[list[str]],
        text_template: str,
        subject_template: Optional[str],
    ) -> bool:
        """Отправляет email."""
        issue_key = issue['key']

        subject = subject_template or f'Re: {issue_key}: {issue["summary"]}'

        try:
            self.yt_manager.create_comment_like_email_and_send(
                email_from=self.email_parser.email_login,
                issue_key=issue_key,
                subject=subject,
                text=text_template,
                to=email_to,
                cc=email_to_cc,
            )
            return True
        except Exception as e:
            auto_yt_emails_logger.exception(
                f'Ошибка отправки автоответа для {issue_key}: {e}'
            )
            return False

    def notify_operator_issue_in_work(
        self, issue: dict, incident: Incident
    ) -> bool:
        """
        Уведомляем оператора о закрытии заявки с обработкой ошибок и
        меняем статус инцидента.
        """
        issue_key: str = issue['key']

        first_email = (
            EmailMessage.objects.filter(
                email_incident=incident, is_first_email=True
            )
            .order_by(
                'email_incident_id', 'email_date', '-is_first_email', 'id'
            )
        ).first()
        email_to = [] if not first_email else [first_email.email_from]

        notify_before_message = (
            'Диспетчер отправил автоответ о принятии заявки в работу '
            'заявителю.'
        )
        success_message = 'Уведомили оператора о принятии заявки в работу.'
        error_message = (
            'Не удалось уведомить оператора о принятии заявки в работу.')

        to_addresses = list(
            first_email.email_msg_to.values_list('email_to', flat=True)
        ) if first_email else []

        cc_addresses = list(
            first_email.email_msg_cc.values_list('email_to', flat=True)
        ) if first_email else []

        all_recipients = set(to_addresses) | set(cc_addresses)
        all_recipients -= set(email_to)

        IncidentManager.add_notify_op_status(incident, notify_before_message)

        result = self.send_auto_reply(
            issue=issue,
            incident=incident,
            email_to=email_to,
            email_to_cc=list(all_recipients),
            success_status_key=(
                self.yt_manager.notified_op_issue_in_work_status_key
            ),
            success_message=success_message,
            text_template=f'Заявка "{issue_key}" принята в работу.',
            error_message=error_message,
        )

        if result:
            IncidentManager.add_notified_op_status(incident, success_message)
        else:
            if incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(incident, error_message)

        return result

    def notify_operator_issue_close(
        self, issue: dict, incident: Incident
    ) -> bool:
        """
        Уведомляем оператора о закрытии заявки с обработкой ошибок и меняем
        статус инцидента.
        """
        issue_key: str = issue['key']

        first_email = (
            EmailMessage.objects.filter(
                email_incident=incident, is_first_email=True
            )
            .order_by(
                'email_incident_id', 'email_date', '-is_first_email', 'id'
            )
        ).first()
        email_to = [] if not first_email else [first_email.email_from]

        notify_before_message = (
            'Диспетчер отправил автоответ заявителю о закрытии заявки.'
        )
        success_message = 'Уведомили оператора о закрытии заявки.'
        error_message = 'Не удалось уведомить оператора о закрытии заявки.'

        to_addresses = list(
            first_email.email_msg_to.values_list('email_to', flat=True)
        ) if first_email else []

        cc_addresses = list(
            first_email.email_msg_cc.values_list('email_to', flat=True)
        ) if first_email else []

        all_recipients = set(to_addresses) | set(cc_addresses)
        all_recipients -= set(email_to)

        IncidentManager.add_notify_op_end_status(
            incident, notify_before_message
        )

        result = self.send_auto_reply(
            issue=issue,
            incident=incident,
            email_to=email_to,
            email_to_cc=list(all_recipients),
            success_status_key=(
                self.yt_manager.notified_op_issue_closed_status_key
            ),
            success_message=success_message,
            text_template=f'Заявка "{issue_key}" закрыта.',
            error_message=error_message,
        )

        if result:
            IncidentManager.add_notified_op_end_status(
                incident, success_message)
        else:
            if incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(incident, error_message)

        return result

    def notify_avr_contractor(
        self, issue: dict, incident: Incident
    ) -> bool:
        """
        Передаем завку в работу подрядчику с обработкой ошибок и
        меняем статус инцидента.
        """
        issue_key: str = issue['key']

        email_to = IncidentManager.get_avr_emails(incident)

        if not email_to:
            comment = 'Не найден email подрядчика для автоответа.' if (
                incident.pole
            ) else (
                'Чтобы передать заявку подрядчику, необходимо указать шифр '
                'опоры и/или номер базовой станции.'
            )
            self._handle_error(issue_key, incident, comment)
            return False

        notify_before_message = (
            'Диспетчер отправил автоответ подрядчику с информацией по заявке.')
        success_message = 'Уведомили подрядчика о заявке.'
        error_message = 'Не удалось уведомить подрядчика о заявке.'

        IncidentManager.add_notify_avr_status(
            incident, notify_before_message)

        result = self.send_auto_reply(
            issue=issue,
            incident=incident,
            email_to=email_to,
            success_status_key=(
                self.yt_manager.notified_avr_in_work_status_key
            ),
            success_message=success_message,
            text_template=self._prepare_incident_text_for_avr(incident),
            error_message=error_message,
        )

        if result:
            IncidentManager.add_notified_avr_status(incident, success_message)
        else:
            if incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(incident, error_message)

        return result

    def _prepare_incident_text_for_avr(self, incident: Incident) -> str:
        text_parts = ['На вас назначен новый инцидент.\n']

        if incident.pole:
            text_parts.append('**ИНФОРМАЦИЯ ОБ ОПОРЕ:**')
            text_parts.append(f'   • Шифр опоры: {incident.pole.pole}')
            text_parts.append(f'   • Регион: {incident.pole.region}')
            text_parts.append(f'   • Адрес: {incident.pole.address}')
            if incident.pole.pole_latitude and incident.pole.pole_longtitude:
                text_parts.append(
                    f'   • Координаты: {incident.pole.pole_latitude}, '
                    f'{incident.pole.pole_longtitude}'
                )

        if incident.base_station:
            text_parts.append('\n**ИНФОРМАЦИЯ О БАЗОВОЙ СТАНЦИИ:**')
            text_parts.append(
                f'   • Номер БС: {incident.base_station.bs_name}')
            if incident.base_station.operator.exists():
                operators = ', '.join(
                    [
                        op.operator_name
                        for op in incident.base_station.operator.all()
                    ]
                )
                text_parts.append(f'   • Операторы: {operators}')

        text_parts.append('\n**ДЕТАЛИ ИНЦИДЕНТА:**')
        text_parts.append(
            f'   • Подрядчик по АВР: {incident.avr_contractor.contractor_name}'
        )
        text_parts.append(
            '   • Дата регистрации: '
            f'{incident.incident_date.astimezone(CURRENT_TZ):%d.%m.%Y %H:%M}'
        )

        if incident.sla_deadline:
            sla_deadline_2_repr = incident.sla_deadline.astimezone(CURRENT_TZ)
            text_parts.append(
                f'   • SLA дедлайн: {sla_deadline_2_repr:%d.%m.%Y %H:%M}'
            )

        if incident.incident_type:
            text_parts.append(
                f'   • Тип инцидента: {incident.incident_type.name}')
            if incident.incident_type.description:
                text_parts.append(
                    f'   • Описание типа: {incident.incident_type.description}'
                )

        emails = (
            EmailMessage.objects.filter(email_incident=incident)
            .order_by(
                'email_incident_id', 'email_date', '-is_first_email', 'id'
            )
        )

        if emails:
            text_parts.append('\n**ИСТОРИЯ ПЕРЕПИСКИ:**')
            counter_email = 0

            for email in emails:
                if email.email_body:
                    email_text = email.email_body.strip()
                    if len(email_text) > MAX_PREVIEW_TEXT_LEN:
                        email_text = email_text[:MAX_PREVIEW_TEXT_LEN] + ' ...'

                    eml_datetime = email.email_date.astimezone(CURRENT_TZ)
                    counter_email += 1

                    text_parts.append(
                        f'\n**Сообщение №{counter_email}** '
                        f'({eml_datetime:%d.%m.%Y %H:%M}):'
                    )

                    # Тело письма в блоке кода:
                    email_text = email_text.replace('```', '')
                    text_parts.append(f'```\n{email_text}\n```')
                    text_parts.append('---')

        text_parts.append('\n\n**ВАЖНО:** НЕ МЕНЯЙТЕ ТЕМУ ПИСЬМА ПРИ ОТВЕТЕ')

        return '\n'.join(text_parts)

    def auto_reply_incident_is_closed(
        self, issue: dict, email: EmailMessage
    ) -> bool:
        """
        Уведомляем заявителя о том, что заявка уже закрыта.
        """
        email_to = [email.email_from]

        success_message = 'Уведомили заявителя о том, что заявка уже закрыта.'
        error_message = (
            'Не удалось уведомить заявителя о том, что заявка уже закрыта.')

        to_addresses = list(
            email.email_msg_to.values_list('email_to', flat=True)
        )

        cc_addresses = list(
            email.email_msg_cc.values_list('email_to', flat=True)
        )

        all_recipients = set(to_addresses) | set(cc_addresses)
        all_recipients -= set(email_to)

        incident = email.email_incident

        text_parts = [
            'Добрый день,\n',
            (
                'Ваше сообщение было отправлено с темой уже закрытого '
                'инцидента либо является ответом на него.'
            ),
            (
                'Если у вас есть новая актуальная информация, пожалуйста, '
                'направьте её отдельным письмом в виде новой заявки.'
            ),

        ]

        if email.email_body:
            preview = email.email_body.strip()
            if len(preview) > MAX_PREVIEW_TEXT_LEN:
                preview = preview[:MAX_PREVIEW_TEXT_LEN].rstrip() + ' ...'

            text_parts.append('\n\nДля справки, фрагмент вашего письма:\n')
            text_parts.append(f'```\n{preview}\n```')

        result = self.send_auto_reply(
            issue=issue,
            incident=incident,
            email_to=email_to,
            email_to_cc=list(all_recipients),
            success_status_key=(
                self.yt_manager.notified_op_issue_in_work_status_key
            ),
            success_message=success_message,
            text_template='\n'.join(text_parts),
            error_message=error_message,
        )

        if not result:
            if incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(incident, error_message)

        return result

    def notify_avr_issue_close(
        self, issue: dict, incident: Incident
    ) -> bool:
        """
        Уведомляем подрядчика о закрытии заявки.
        """
        issue_key: str = issue['key']

        email_to = IncidentManager.get_avr_emails(incident)

        notify_before_message = (
            'Диспетчер отправил автоответ подрядчику о закрытии заявки.'
        )
        success_message = 'Уведомили подрядчика о закрытии заявки.'
        error_message = 'Не удалось уведомить подрядчика о закрытии заявки.'

        IncidentManager.add_notify_op_end_status(
            incident, notify_before_message)

        result = self.send_auto_reply(
            issue=issue,
            incident=incident,
            email_to=email_to,
            email_to_cc=None,
            success_status_key=(
                self.yt_manager.notified_op_issue_closed_status_key
            ),
            success_message=success_message,
            text_template=f'Заявка "{issue_key}" закрыта.',
            error_message=error_message,
        )

        if result:
            # Т.к. статус будет выставлен до этого, уведомление добавляем
            # вручную:
            self.yt_manager.create_comment(
                issue_key=issue_key,
                comment=success_message,
            )

        if not result:
            if incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(incident, error_message)

        return result
