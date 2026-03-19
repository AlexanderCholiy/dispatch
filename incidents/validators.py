import re
from typing import Optional

from django.db.models import QuerySet
from django.db.models.functions import Length

from emails.models import EmailMessage

from .constants import (
    AVR_CATEGORY,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFIED_OP_END_STATUS_NAME,
    NOTIFIED_OP_IN_WORK_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_NAME,
    NOTIFY_OP_END_STATUS_NAME,
    NOTIFY_OP_IN_WORK_STATUS_NAME,
    RVR_CATEGORY,
    STATUS_TRANSITIONS,
)
from .models import BaseStation, Incident, IncidentStatus, Pole


class IncidentValidator:

    def _find_num_in_text(self, text: str) -> set[str]:
        """Извлекает слова с минимум 4 цифрами (столько содержит номер БС)."""
        symbols_2_replace: set[str] = {
            '[', ']', '{', '}', '(', ')', '<', '>',  # скобки
            ':', ';', ',', '.', '|', '/', '\\',  # разделители
            "'", '"', '`',  # кавычки
            'БС-', 'бс-',  # метки для станций
        }

        exclude_pattern: set[re.Pattern] = {
            re.compile(r'\bIP:\s*\S+', re.IGNORECASE),
            re.compile(r'\bTel:\s*\S+', re.IGNORECASE),
            re.compile(r'\bmob:\s*\S+', re.IGNORECASE),
        }

        new_text = text

        for pattern in exclude_pattern:
            new_text = pattern.sub('', new_text)

        for symbol in symbols_2_replace:
            new_text = new_text.replace(symbol, ' ')

        words = new_text.split()

        result = []
        for word in words:
            word = word.strip()

            if not word:
                continue

            # Подсчитываем цифры в слове (включая те, что идут через дефисы):
            digit_count = sum(1 for char in word if char.isdigit())
            if digit_count >= 4:
                result.append(word)

        return set(result)

    def _clean_email_text(self, text: str) -> str:
        """Тело сообщения, без цитирование и подписи."""
        if not text:
            return ''

        # 1. Удаляем блоки цитирования (строки, начинающиеся с >)
        text = re.sub(r'(?m)^>.*$', '', text)

        # 2. Маркеры начала подписи или истории переписки
        split_markers = [
            r'--\s*',                       # Стандартный разделитель подписи
            r'С\s+уважением,?',             # "С уважением" (с запятой или без)
            r'From:',                       # Outlook/стандарт
            r'От кого:',                    # Русская версия Outlook
            r'Sent:',                       # Дата/время отправки
            r'Дата:',
            r'[\w\.-]+@[\w\.-]+\.\w+',      # Email адрес (без скобок)
            r'(?:Понедельник|Вторник|Среда|Четверг|Пятница|Суббота|Воскресенье),'  # noqa: E501
        ]

        pattern = '|'.join(split_markers)

        # Используем split и берем первую часть (самое свежее сообщение)
        parts = re.split(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        clean_text = parts[0].strip()

        return clean_text

    def _find_pole_in_text(self, text: str) -> QuerySet[Pole]:
        """
        Поиск опоры по самому длинному найденному шифру в тексте.

        Возвращает QuerySet из одной или нескольких опор, если они совпадают с
        самым длинным словом.
        """
        clean_text = self._clean_email_text(text)

        result = []

        for word in self._find_num_in_text(clean_text):
            pattern = r'\d{5}-'
            if re.match(pattern, word):
                poles = Pole.objects.filter(pole__istartswith=word)
            else:
                poles = Pole.objects.filter(pole=word)

            if poles.exists():
                result.append((word, list(poles)))

        if not result:
            return Pole.objects.none()

        longest_word, longest_poles = max(result, key=lambda x: len(x[0]))

        return Pole.objects.filter(id__in=[p.id for p in longest_poles])

    def _find_base_station_in_text(self, text: str) -> QuerySet[BaseStation]:
        """
        Поиск BaseStation по самому длинному найденному шифру в тексте.

        Если найдена опора, фильтруем BaseStation по этой опоре.
        Возвращает QuerySet из одной или нескольких базовых станций,
        соответствующих самому длинному слову.
        """
        result = []
        poles = self._find_pole_in_text(text)
        clean_text = self._clean_email_text(text)

        for word in self._find_num_in_text(clean_text):
            bs_stations = BaseStation.objects.filter(
                bs_name__icontains=word
            ).annotate(
                name_length=Length('bs_name')
            ).order_by('name_length')

            if poles.exists():
                bs_stations = bs_stations.filter(pole__in=poles)

            if bs_stations.exists():
                result.append((word, list(bs_stations)))

        if not result:
            return BaseStation.objects.none()

        longest_word, longest_bs = max(result, key=lambda x: len(x[0]))

        return BaseStation.objects.filter(id__in=[bs.id for bs in longest_bs])

    def find_pole_and_base_station_in_text(
        self, text: str
    ) -> tuple[Optional[Pole], Optional[BaseStation]]:
        """Поиск Pole и BaseStation в тексте."""
        poles_qs = self._find_pole_in_text(text)
        bs_qs = self._find_base_station_in_text(text)

        bs = bs_qs.first() if bs_qs.exists() else None
        pole = bs.pole if bs else (
            poles_qs.first() if poles_qs.exists() else None
        )

        return pole, bs

    def find_pole_and_base_station_in_msg(
        self, msg: EmailMessage
    ) -> tuple[Optional[Pole], Optional[BaseStation]]:
        """Поиск Pole и BaseStation в теме или теле письма."""
        if msg.email_subject:
            pole, base_station = (
                self.find_pole_and_base_station_in_text(msg.email_subject)
            )
            if pole is not None:
                return pole, base_station

        if msg.email_body:
            pole, base_station = (
                self.find_pole_and_base_station_in_text(msg.email_body)
            )
            if pole is not None:
                return pole, base_station

        return None, None


def validate_status_transition(
    last_status: Optional[IncidentStatus],
    next_status_name: str,
) -> Optional[str]:
    """Проверяет допустимость перехода между статусами."""

    if not last_status:
        return None

    allowed_transitions = STATUS_TRANSITIONS.get(last_status.name, [])

    if next_status_name not in allowed_transitions:
        return (
            'Недопустимый переход из статуса '
            f'«{last_status.name}» в «{next_status_name}».'
        )

    return None


def validate_notify_operator(
    incident: Incident, last_status: Optional[IncidentStatus]
) -> Optional[str]:
    if (
        last_status
        and last_status.name in (
            NOTIFY_OP_IN_WORK_STATUS_NAME, NOTIFIED_OP_IN_WORK_STATUS_NAME
        )
    ):
        return (
            f'Инцидент {incident} уже находится в статусе '
            f'«{last_status.name}».'
        )

    transition_error = validate_status_transition(
        last_status,
        NOTIFIED_OP_IN_WORK_STATUS_NAME,
    )
    if transition_error:
        return transition_error


def validate_notify_incident_closed(
    incident: Incident, last_status: Optional[IncidentStatus]
) -> Optional[str]:
    if (
        last_status
        and last_status.name in (
            NOTIFY_OP_END_STATUS_NAME, NOTIFIED_OP_END_STATUS_NAME
        )
    ):
        return (
            f'Инцидент {incident} уже находится в статусе '
            f'«{last_status.name}».'
        )

    transition_error = validate_status_transition(
        last_status,
        NOTIFIED_OP_END_STATUS_NAME,
    )
    if transition_error:
        return transition_error


def validate_notify_avr(
    incident: Incident,
    last_status: Optional[IncidentStatus],
    category_names: set[str],
) -> Optional[str]:
    if (
        last_status
        and last_status.name in (
            NOTIFY_CONTRACTOR_STATUS_NAME,
            NOTIFIED_CONTRACTOR_STATUS_NAME,
        )
    ):
        return (
            f'Инцидент {incident} уже находится в статусе '
            f'«{last_status.name}».'
        )

    if not incident.pole:
        return (
            f'Перед передачей инцидента {incident} '
            f'на РВР необходимо указать шифр опоры.'
        )

    if AVR_CATEGORY not in category_names:
        return (
            f'Перед передачей инцидента {incident} '
            f'на РВР необходимо добавить категорию «{AVR_CATEGORY}».'
        )

    if not incident.incident_type:
        return (
            'Необходимо выбрать тип проблемы прежде чем '
            'отправить заявку на АВР.'
        )

    transition_error = validate_status_transition(
        last_status,
        NOTIFIED_CONTRACTOR_STATUS_NAME,
    )
    if transition_error:
        return transition_error

    return None


def validate_notify_rvr(
    incident: Incident,
    last_status: Optional[IncidentStatus],
    category_names: set[str],
) -> Optional[str]:
    if (
        last_status
        and last_status.name in (
            NOTIFY_CONTRACTOR_STATUS_NAME,
            NOTIFIED_CONTRACTOR_STATUS_NAME,
        )
    ):
        return (
            f'Инцидент {incident} уже находится в статусе '
            f'«{last_status.name}».'
        )

    if not incident.pole:
        return (
            f'Перед передачей инцидента {incident} '
            'на РВР необходимо указать шифр опоры.'
        )

    if RVR_CATEGORY not in category_names:
        return (
            f'Перед передачей инцидента {incident} '
            f'на РВР необходимо добавить категорию «{RVR_CATEGORY}».'
        )

    transition_error = validate_status_transition(
        last_status,
        NOTIFIED_CONTRACTOR_STATUS_NAME,
    )
    if transition_error:
        return transition_error

    return None
