import re
from typing import Callable, Optional

from core.constants import YANDEX_TRACKER_AUTO_EMAILS_ROTATING_FILE
from core.loggers import LoggerFactory
from emails.email_parser import EmailParser
from emails.models import EmailMessage
from incidents.constants import (
    DEFAULT_AVR_CATEGORY,
    DEFAULT_ERR_STATUS_NAME,
    DEFAULT_RVR_CATEGORY,
)
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
        issue: dict,
        incident: Incident,
    ):
        self.yt_manager = yt_manager
        self.email_parser = email_parser
        self.issue = issue
        self.incident = incident

        self.issue_key: str = issue['key']

    def send_auto_reply(
        self,
        email_to: list[str],
        text_template: str,
        success_status_key: str,
        email_to_cc: Optional[list[str]] = None,
        subject_template: Optional[str] = None,
        success_message: Optional[str] = None,
        error_message: Optional[str] = None,
        change_status: bool = True,
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
            email_sender_func: Функция отправки email
            text_template: Шаблон текста письма

        Kwargs:
            notify_before_message: Сообщение для обновления статуса инцидента
            subject_template: Шаблон темы письма
            success_message: Сообщение для статуса при успехе
            error_message: Сообщение об ошибке
            email_to_cc: Получатели в копии

        Returns:
            bool: Успешность отправки
        """
        success_message = success_message or (
            'Автоматический ответ отправлен'
        )
        error_message = error_message or (
            'Не удалось отправить автоматический ответ'
        )

        email_to_cc = email_to_cc if email_to_cc else []

        if (
            self.email_parser.email_login not in email_to_cc
            and self.email_parser.email_login not in email_to
        ):
            email_to_cc.append(self.email_parser.email_login)

        success_sent_email = self._send_email(
            email_to, email_to_cc, text_template, subject_template
        )

        if change_status:
            if success_sent_email:
                self.yt_manager.update_issue_status(
                    self.issue_key, success_status_key, success_message
                )
            else:
                self._handle_error(error_message)

        return success_sent_email

    def _handle_error(self, error_message: str) -> None:
        """Обрабатывает ошибку отправки."""
        was_status_update = self.yt_manager.update_issue_status(
            self.issue_key, self.yt_manager.error_status_key, error_message
        )
        if was_status_update:
            auto_yt_emails_logger.debug(error_message)
            IncidentManager.add_error_status(self.incident, error_message)

    def _send_email(
        self,
        email_to: list[str],
        email_to_cc: Optional[list[str]],
        text_template: str,
        subject_template: Optional[str],
    ) -> bool:
        """Отправляет email."""
        subject = (
            subject_template
            or f'Re: {self.issue_key}: {self.issue["summary"]}'
        )

        try:
            self.yt_manager.create_comment_like_email_and_send(
                email_from=self.email_parser.email_login,
                issue_key=self.issue_key,
                subject=subject,
                text=text_template,
                to=email_to,
                cc=email_to_cc,
            )
            return True
        except Exception as e:
            auto_yt_emails_logger.exception(
                f'Ошибка отправки автоответа для {self.issue_key}: {e}'
            )
            return False

    def notify_operator_issue_in_work(self) -> bool:
        """
        Уведомляем оператора о закрытии заявки с обработкой ошибок и
        меняем статус инцидента.
        """
        first_email = (
            EmailMessage.objects.filter(
                email_incident=self.incident, is_first_email=True
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

        IncidentManager.add_notify_op_status(
            self.incident, notify_before_message
        )

        result = self.send_auto_reply(
            email_to=email_to,
            email_to_cc=list(all_recipients),
            success_status_key=(
                self.yt_manager.notified_op_issue_in_work_status_key
            ),
            success_message=success_message,
            text_template=f'Заявка "{self.issue_key}" принята в работу.',
            error_message=error_message,
        )

        if result:
            IncidentManager.add_notified_op_status(
                self.incident, success_message
            )
        else:
            if self.incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(self.incident, error_message)

        return result

    def notify_operator_issue_close(self) -> bool:
        """
        Уведомляем оператора о закрытии заявки с обработкой ошибок и меняем
        статус инцидента.
        """
        first_email = (
            EmailMessage.objects.filter(
                email_incident=self.incident, is_first_email=True
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
            self.incident, notify_before_message
        )

        result = self.send_auto_reply(
            email_to=email_to,
            email_to_cc=list(all_recipients),
            success_status_key=(
                self.yt_manager.notified_op_issue_closed_status_key
            ),
            success_message=success_message,
            text_template=f'Заявка "{self.issue_key}" закрыта.',
            error_message=error_message,
        )

        if result:
            IncidentManager.add_notified_op_end_status(
                self.incident, success_message
            )
        else:
            if self.incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(self.incident, error_message)

        return result

    def _notify_avr_contractor(self) -> bool:
        email_to = IncidentManager.get_avr_emails(self.incident)

        if not email_to:
            comment = 'Не найден email подрядчика АВР для автоответа.'
            self._handle_error(comment)
            return False

        subject_raw: str = self.issue['summary']
        cleaned_subject = re.sub(
            r'^(?:\s*Re:\s*)+', '', subject_raw, flags=re.IGNORECASE
        )
        subject_template = f'{self.issue_key}: {cleaned_subject}'

        result = self.send_auto_reply(
            email_to=email_to,
            success_status_key=(
                self.yt_manager.notified_avr_in_work_status_key
            ),
            text_template=self._prepare_incident_text_for_avr(),
            subject_template=subject_template,
            change_status=False,
        )

        return result

    def _notify_rvr_contractor(self) -> bool:
        email_to = None
        if (
            self.incident.pole
            and self.incident.pole.region
            and self.incident.pole.region.rvr_email
        ):
            email_to = [self.incident.pole.region.rvr_email.email]

        if not email_to:
            comment = 'Не найден email подрядчика РВР для автоответа.'
            self._handle_error(comment)
            return False

        subject_raw: str = self.issue['summary']
        cleaned_subject = re.sub(
            r'^(?:\s*Re:\s*)+', '', subject_raw, flags=re.IGNORECASE
        )
        subject_template = f'{self.issue_key}: {cleaned_subject}'

        result = self.send_auto_reply(
            email_to=email_to,
            success_status_key=(
                self.yt_manager.notified_avr_in_work_status_key
            ),
            text_template=self._prepare_incident_text_for_rvr(),
            subject_template=subject_template,
            change_status=False,
        )

        return result

    def notify_contractors(self, category_field: dict) -> bool:
        """
        Передаем завку в работу подрядчикам (АВР, РВР) с обработкой ошибок и
        меняем статус инцидента.
        """
        category_field_key = category_field['id']
        categories: Optional[list[str]] = self.issue.get(category_field_key)

        target_categories = {
            DEFAULT_AVR_CATEGORY: self._notify_avr_contractor,
            DEFAULT_RVR_CATEGORY: self._notify_rvr_contractor,
        }

        selected_categories = [
            cat for cat in (DEFAULT_AVR_CATEGORY, DEFAULT_RVR_CATEGORY)
            if categories and cat in categories
        ]

        if not selected_categories:
            comment = (
                'Чтобы передать заявку подрядчикам, необходимо выбрать '
                'категорию инцидента АВР и/или РВР.'
            )
            self._handle_error(comment)
            return False

        if not self.incident.pole:
            comment = (
                'Чтобы передать заявку подрядчикам, необходимо указать шифр '
                'опоры и/или номер базовой станции.'
            )
            self._handle_error(comment)
            return False

        IncidentManager.add_notify_avr_status(
            self.incident,
            f'Диспетчер отправил автоответ подрядчикам по: '
            f'{", ".join(selected_categories)} с информацией по заявке.'
        )

        success_categories = []
        failed_categories = []

        for category in selected_categories:
            notify_func: Callable = target_categories[category]
            result = notify_func()
            (
                success_categories if result else failed_categories
            ).append(category)

        if failed_categories:
            error_message = (
                'Не удалось уведомить подрядчиков: '
                f'{", ".join(failed_categories)} о новой заявке.'
            )
            self._handle_error(error_message)
            IncidentManager.add_error_status(self.incident, error_message)
            return False

        success_message = (
            'Подрядчики по: '
            f'{", ".join(success_categories)} уведомлены о новой заявке.'
        )
        self.yt_manager.update_issue_status(
            self.issue_key,
            self.yt_manager.notified_avr_in_work_status_key,
            success_message,
        )
        IncidentManager.add_notified_avr_status(self.incident, success_message)
        return True

    def _prepare_incident_text_for_rvr(self) -> str:
        return 'Новая заявка на РВР'

    def _prepare_incident_text_for_avr(self) -> str:
        text_parts = ['На вас назначен новый инцидент.\n']

        if self.incident.pole:
            pole_region = (
                self.incident.pole.region.region_ru
                or self.incident.pole.region.region_en
            ) if self.incident.pole.region else None

            text_parts.append('**ИНФОРМАЦИЯ ОБ ОПОРЕ:**')
            text_parts.append(f'   • Шифр опоры: {self.incident.pole.pole}')

            if pole_region:
                text_parts.append(f'   • Регион: {pole_region}')

            if self.incident.pole.address:
                text_parts.append(f'   • Адрес: {self.incident.pole.address}')

            if (
                self.incident.pole.pole_latitude
                and self.incident.pole.pole_longtitude
            ):
                text_parts.append(
                    f'   • Координаты: {self.incident.pole.pole_latitude}, '
                    f'{self.incident.pole.pole_longtitude}'
                )

        if self.incident.base_station:
            text_parts.append('\n**ИНФОРМАЦИЯ О БАЗОВОЙ СТАНЦИИ:**')
            text_parts.append(
                f'   • Номер БС: {self.incident.base_station.bs_name}')
            if self.incident.base_station.operator.exists():
                operators = ', '.join(
                    [
                        op.operator_name
                        for op in self.incident.base_station.operator.all()
                    ]
                )
                text_parts.append(f'   • Операторы: {operators}')

        text_parts.append('\n**ДЕТАЛИ ИНЦИДЕНТА:**')
        text_parts.append(
            '   • Подрядчик по АВР: '
            f'{self.incident.avr_contractor.contractor_name}'
        )
        text_parts.append(
            '   • Дата регистрации: '
            f'{self.incident.incident_date.astimezone(CURRENT_TZ):%d.%m.%Y %H:%M}'  # noqa: E501
        )

        if self.incident.sla_deadline:
            text_parts.append(
                f'   • SLA дедлайн: {self.incident.sla_deadline.astimezone(CURRENT_TZ):%d.%m.%Y %H:%M}'  # noqa: E501
            )

        if self.incident.incident_type:
            text_parts.append(
                f'   • Тип инцидента: {self.incident.incident_type.name}')
            if self.incident.incident_type.description:
                text_parts.append(
                    '   • Описание типа: '
                    f'{self.incident.incident_type.description}'
                )

        emails = (
            EmailMessage.objects.filter(email_incident=self.incident)
            .order_by(
                'email_incident_id', 'email_date', '-is_first_email', 'id'
            )
        )

        if emails.exists():
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

    def auto_reply_incident_is_closed(self, email: EmailMessage) -> bool:
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

    def notify_avr_issue_close(self) -> bool:
        """
        Уведомляем подрядчика АВР о закрытии заявки.
        """
        email_to = IncidentManager.get_avr_emails(self.incident)

        notify_before_message = (
            'Диспетчер отправил автоответ подрядчику о закрытии заявки.'
        )
        success_message = 'Уведомили подрядчика АВР о закрытии заявки.'
        error_message = (
            'Не удалось уведомить подрядчика АВР о закрытии заявки.'
        )

        IncidentManager.add_notify_op_end_status(
            self.incident, notify_before_message
        )

        result = self.send_auto_reply(
            email_to=email_to,
            email_to_cc=None,
            success_status_key=(
                self.yt_manager.notified_op_issue_closed_status_key
            ),
            success_message=success_message,
            text_template=f'Заявка "{self.issue_key}" закрыта.',
            error_message=error_message,
        )

        if result:
            # Т.к. статус будет выставлен до этого, уведомление добавляем
            # вручную:
            self.yt_manager.create_comment(
                issue_key=self.issue_key,
                comment=success_message,
            )

        if not result:
            if self.incident.prefetched_statuses[0] != DEFAULT_ERR_STATUS_NAME:
                IncidentManager.add_error_status(self.incident, error_message)

        return result
