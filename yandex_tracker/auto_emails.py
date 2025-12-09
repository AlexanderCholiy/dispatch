import re
from typing import Callable, Optional

from django.utils import timezone

from core.loggers import yt_emails_logger
from emails.email_parser import EmailParser
from emails.models import EmailMessage
from incidents.constants import (
    AVR_CATEGORY,
    ERR_STATUS_NAME,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_NAME,
    RVR_CATEGORY,
)
from incidents.models import Incident
from incidents.utils import IncidentManager

from .constants import CURRENT_TZ, MAX_PREVIEW_TEXT_LEN
from .utils import YandexTrackerManager


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
            yt_emails_logger.debug(error_message)
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
            yt_emails_logger.exception(
                f'Ошибка отправки автоответа для {self.issue_key}: {e}'
            )
            return False

    def notify_operator_issue_in_work(self) -> bool:
        """
        Уведомляем оператора о принятии заявки с обработкой ошибок и
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
            if self.incident.prefetched_statuses[0] != ERR_STATUS_NAME:
                IncidentManager.add_error_status(self.incident, error_message)

        return result

    def _notify_operator_issue_close(self) -> bool:
        """Уведомляем оператора о закрытии заявки."""
        first_email = (
            EmailMessage.objects.filter(
                email_incident=self.incident, is_first_email=True
            )
            .order_by(
                'email_incident_id', 'email_date', '-is_first_email', 'id'
            )
        ).first()
        email_to = [] if not first_email else [first_email.email_from]

        to_addresses = list(
            first_email.email_msg_to.values_list('email_to', flat=True)
        ) if first_email else []

        cc_addresses = list(
            first_email.email_msg_cc.values_list('email_to', flat=True)
        ) if first_email else []

        all_recipients = set(to_addresses) | set(cc_addresses)
        all_recipients -= set(email_to)

        result = self.send_auto_reply(
            email_to=email_to,
            email_to_cc=list(all_recipients),
            success_status_key=(
                self.yt_manager.notified_op_issue_closed_status_key
            ),
            text_template=f'Заявка "{self.issue_key}" закрыта.',
            change_status=False,
        )

        return result

    @property
    def _re_cleaned_subject(self) -> str:
        subject_row: str = self.issue['summary']
        cleaned_subject = re.sub(
            r'^(?:\s*Re:\s*)+', '', subject_row, flags=re.IGNORECASE
        )
        return f'{self.issue_key}: {cleaned_subject}'

    def _notify_contractor_issue_close(
        self, email_to: list[str], text_tmp: str = ''
    ) -> bool:
        """Уведомляем подрядчиков о закрытии заявки."""
        text_tmp = text_tmp or f'Заявка "{self.issue_key}" закрыта.'

        result = self.send_auto_reply(
            email_to=email_to,
            email_to_cc=None,
            success_status_key=(
                self.yt_manager.notified_op_issue_closed_status_key
            ),
            subject_template=self._re_cleaned_subject,
            text_template=text_tmp,
            change_status=False,
        )

        return result

    def notify_issue_close(self, category_field: dict) -> bool:
        success_results = []
        failed_results = []

        result = self._notify_operator_issue_close()
        if result:
            success_results.append('Заявитель')
        else:
            failed_results.append('заявителя')

        category_field_key = category_field['id']
        categories: Optional[list[str]] = self.issue.get(category_field_key)

        if (
            not failed_results
            and categories
            and any(cat in categories for cat in (AVR_CATEGORY, RVR_CATEGORY))
        ):
            incident_emails = IncidentManager.all_incident_emails(
                self.incident
            )
            incident_status_names: set[str] = {
                st.name for st in self.incident.statuses.all()
            }
            avr_contractor_emails = set(
                IncidentManager.get_avr_emails(self.incident)
            )
            rvr_contractor_emails = set(
                IncidentManager.get_rvr_emails(self.incident)
            )

            # Условия при которых необходимо также уведомить
            # подрядчиков о закрытии инцидента:
            if (
                avr_contractor_emails
                and (
                    AVR_CATEGORY in categories
                    and (
                        any(
                            s in incident_status_names for s in (
                                NOTIFIED_CONTRACTOR_STATUS_NAME,
                                NOTIFY_CONTRACTOR_STATUS_NAME,
                            )
                        )
                        or not avr_contractor_emails.isdisjoint(
                            incident_emails
                        )
                    )
                )
            ):
                text_tmp = f'Заявка "{self.issue_key}" (АВР) закрыта.'
                result = self._notify_contractor_issue_close(
                    avr_contractor_emails, text_tmp
                )
                if result:
                    success_results.append(f'подрядчик по {AVR_CATEGORY}')
                else:
                    failed_results.append(f'подрядчика по {AVR_CATEGORY}')

            if (
                not failed_results
                and rvr_contractor_emails
                and (
                    RVR_CATEGORY in categories
                    and (
                        any(
                            s in incident_status_names for s in (
                                NOTIFIED_CONTRACTOR_STATUS_NAME,
                                NOTIFY_CONTRACTOR_STATUS_NAME,
                            )
                        )
                        or not rvr_contractor_emails.isdisjoint(
                            incident_emails
                        )
                    )
                )
            ):
                text_tmp = f'Заявка "{self.issue_key}" (РВР) закрыта.'
                result = self._notify_contractor_issue_close(
                    rvr_contractor_emails, text_tmp
                )
                if result:
                    success_results.append(f'подрядчик по {RVR_CATEGORY}')
                else:
                    failed_results.append(f'подрядчика по {RVR_CATEGORY}')

        if failed_results:
            error_message = (
                'Не удалось уведомить: '
                f'{", ".join(failed_results)} о закрытии заявки.'
            )
            self._handle_error(error_message)
            IncidentManager.add_error_status(self.incident, error_message)
            return False

        success_message = (
            f'{", ".join(success_results)} уведомлен(ы) о закрытии заявки.'
        )
        self.yt_manager.update_issue_status(
            self.issue_key,
            self.yt_manager.notified_op_issue_closed_status_key,
            success_message,
        )
        IncidentManager.add_notified_op_end_status(
            self.incident, success_message
        )
        return True

    def _notify_avr_contractor(self) -> bool:
        email_to = IncidentManager.get_avr_emails(self.incident)

        if not email_to:
            comment = 'Не найден email подрядчика АВР для автоответа.'
            self._handle_error(comment)
            return False

        if not self.incident.incident_type:
            comment = (
                'Необходимо выбрать тип проблемы, прежде чем передавать его '
                'подрядчику по АВР.'
            )
            self._handle_error(comment)
            return False

        result = self.send_auto_reply(
            email_to=email_to,
            success_status_key=(
                self.yt_manager.notified_contractor_in_work_status_key
            ),
            text_template=self._prepare_incident_text_for_avr(),
            subject_template=self._re_cleaned_subject,
            change_status=False,
        )

        return result

    def _notify_rvr_contractor(self) -> bool:
        email_to = IncidentManager.get_rvr_emails(self.incident)

        if not email_to:
            comment = 'Не найден email подрядчика РВР для автоответа.'
            self._handle_error(comment)
            return False

        result = self.send_auto_reply(
            email_to=email_to,
            success_status_key=(
                self.yt_manager.notified_contractor_in_work_status_key
            ),
            text_template=self._prepare_incident_text_for_rvr(),
            subject_template=self._re_cleaned_subject,
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
            AVR_CATEGORY: self._notify_avr_contractor,
            RVR_CATEGORY: self._notify_rvr_contractor,
        }

        selected_categories = [
            cat for cat in (AVR_CATEGORY, RVR_CATEGORY)
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

        IncidentManager.add_notify_contractor_status(
            self.incident,
            'Диспетчер отправил автоответ подрядчикам по: '
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
                break

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
            self.yt_manager.notified_contractor_in_work_status_key,
            success_message,
        )
        IncidentManager.add_notified_contractor_status(
            self.incident, success_message
        )
        return True

    def _prepare_incident_text(self, incident_type: str) -> str:
        """
        Подготавливает текст инцидента.

        Args:
            incident_type: 'avr' или 'rvr'
        """
        type_titles = {
            'avr': 'На вас назначен новый инцидент (АВР).',
            'rvr': 'На вас назначен новый инцидент (РВР).'
        }

        text_parts = [f'{type_titles[incident_type]}\n']

        # Общая информация
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
                f'   • Номер БС: {self.incident.base_station.bs_name}'
            )
            if self.incident.base_station.operator.exists():
                operators = ', '.join([
                    op.operator_name
                    for op in self.incident.base_station.operator.all()
                ])
                text_parts.append(f'   • Операторы: {operators}')

        # Детали инцидента
        text_parts.append('\n**ДЕТАЛИ ИНЦИДЕНТА:**')

        if incident_type == 'avr' and self.incident.avr_contractor:
            text_parts.append(
                '   • Подрядчик по АВР: '
                f'{self.incident.avr_contractor.contractor_name}'
            )

        incident_date = (
            self.incident.incident_date
            .astimezone(CURRENT_TZ).strftime('%d.%m.%Y %H:%M')
        )
        text_parts.append(f'   • Дата регистрации: {incident_date}')

        if incident_type == 'avr':
            if not self.incident.avr_start_date:
                self.incident.avr_start_date = timezone.now()
                # save будет потом автоматически
            if self.incident.sla_avr_deadline:
                sla_avr_deadline = (
                    self.incident.sla_avr_deadline
                    .astimezone(CURRENT_TZ).strftime('%d.%m.%Y %H:%M')
                )
                text_parts.append(f'   • SLA дедлайн: {sla_avr_deadline}')
        elif incident_type == 'rvr':
            if not self.incident.rvr_start_date:
                self.incident.rvr_start_date = timezone.now()
                # save будет потом автоматически
            if self.incident.sla_rvr_deadline:
                sla_rvr_deadline = (
                    self.incident.sla_rvr_deadline
                    .astimezone(CURRENT_TZ).strftime('%d.%m.%Y %H:%M')
                )
                text_parts.append(f'   • SLA дедлайн: {sla_rvr_deadline}')

        if incident_type == 'avr' and self.incident.incident_type:
            incident_type_name = self.incident.incident_type.name
            text_parts.append(f'   • Тип инцидента: {incident_type_name}')
            if self.incident.incident_type.description:
                description = self.incident.incident_type.description
                text_parts.append(f'   • Описание типа: {description}')

        # История переписки
        emails = (
            EmailMessage.objects.filter(
                email_incident=self.incident,
                email_body__isnull=False
            )
            .exclude(email_body='')
            .order_by(
                'email_incident_id', 'email_date', '-is_first_email', 'id'
            )
        )

        if emails.exists():
            counter_email = 0
            seen_texts = set()

            for email in emails:
                email_text = email.email_body.strip()
                text_fingerprint = email_text[:128].lower().strip()

                eml_datetime = (
                    email.email_date
                    .astimezone(CURRENT_TZ).strftime('%d.%m.%Y %H:%M')
                )

                if text_fingerprint not in seen_texts:
                    seen_texts.add(text_fingerprint)

                    starts_with_title = any(
                        text_fingerprint.startswith(title.lower().strip())
                        for title in type_titles.values()
                    )
                    if not text_fingerprint or starts_with_title:
                        continue

                    if not counter_email:
                        text_parts.append('\n**ИСТОРИЯ ПЕРЕПИСКИ:**')

                    counter_email += 1

                    if len(email_text) > MAX_PREVIEW_TEXT_LEN:
                        email_text = email_text[:MAX_PREVIEW_TEXT_LEN] + ' ...'

                    text_parts.append(
                        f'\n**Сообщение №{counter_email}** ({eml_datetime}):'
                    )
                    email_text = email_text.replace('```', '')
                    text_parts.append(f'```\n{email_text}\n```')
                    text_parts.append('---')

        text_parts.append('\n\n**ВАЖНО:** НЕ МЕНЯЙТЕ ТЕМУ ПИСЬМА ПРИ ОТВЕТЕ')

        return '\n'.join(text_parts)

    def _prepare_incident_text_for_rvr(self) -> str:
        return self._prepare_incident_text('rvr')

    def _prepare_incident_text_for_avr(self) -> str:
        return self._prepare_incident_text('avr')

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

        # Отправка уведомления без изменения статуса:
        result = self.send_auto_reply(
            email_to=email_to,
            email_to_cc=list(all_recipients),
            success_status_key=(
                self.yt_manager.notified_op_issue_in_work_status_key
            ),
            success_message=success_message,
            text_template='\n'.join(text_parts),
            error_message=error_message,
            change_status=False
        )

        if not result:
            if incident.prefetched_statuses[0] != ERR_STATUS_NAME:
                IncidentManager.add_error_status(incident, error_message)

        return result
