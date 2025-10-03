import re
from typing import Optional

from django.db.models import QuerySet
from django.db.models.functions import Length

from emails.models import EmailMessage

from .models import BaseStation, Pole


class IncidentValidator:

    def _find_num_in_text(self, text: str) -> set[str]:
        """Извлекает слова с минимум 4 цифрами (столько содержит номер БС)."""
        symbols_2_replace: set[str] = {
            '[', ']', '(', ')', '{', '}', ':', '|', ',', '.', ';',
            "'", '"', '`', '/', '\\', 'БС-', 'бс-'
        }
        new_text = text
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

    def _find_pole_in_text(self, text: str) -> QuerySet[Pole]:
        """
        Поиск опоры по самому длинному найденному шифру в тексте.

        Возвращает QuerySet из одной или нескольких опор, если они совпадают с
        самым длинным словом.
        """
        result = []

        for word in self._find_num_in_text(text):
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

        for word in self._find_num_in_text(text):
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
