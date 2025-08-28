import re
from typing import Optional

from emails.models import EmailMessage

from .models import BaseStation, Pole


class IncidentValidator:

    def _find_num_in_text(self, text: str) -> list[str]:
        """Извлекает слова с минимум 4 цифрами (столько содержит номер БС)."""
        symbols_2_replace: set[str] = {
            '[', ']', '(', ')', '{', '}', ':', '|', ',', '.', ';',
            "'", '"', '`'
        }
        new_text = text
        for symbol in symbols_2_replace:
            new_text = new_text.replace(symbol, '')

        words = new_text.split()

        result = []
        for word in words:
            word = word.strip()
            if sum(1 for char in word if char.isdigit()) >= 4:
                result.append(word)
        return result

    def _find_pole_in_text(self, text: str) -> Optional[Pole]:
        """Поиск шифра опоры в тексте."""
        result = []
        for word in self._find_num_in_text(text):
            pattern = r'\d{5}-'
            match = re.match(pattern, word)
            if match:
                pole = (
                    Pole.objects
                    .filter(pole__istartswith=word)
                    .first()
                )
            else:
                pole = Pole.objects.filter(pole=word).first()

            if pole:
                result.append((word, pole))

        if not result:
            return None

        longest_word_tuple = max(result, key=lambda x: len(x[0]))
        return longest_word_tuple[1]

    def _find_base_station_in_text(self, text: str) -> Optional[BaseStation]:
        """Поиск BaseStation в тексте."""
        result = []
        pole = self._find_pole_in_text(text)
        for word in self._find_num_in_text(text):
            bs_stations = BaseStation.objects.filter(bs_name=word)

            if bs_stations:
                for bs_station in bs_stations:
                    if pole and pole != bs_station.pole:
                        continue
                    result.append((word, bs_station))

        if not result:
            return None

        longest_word_tuple = max(result, key=lambda x: len(x[0]))
        return longest_word_tuple[1]

    def find_pole_and_base_station_in_text(self, text: str) -> tuple[
        Optional[Pole], Optional[BaseStation]
    ]:
        """Поиск Pole и BaseStation в тексте."""
        base_stations = self._find_base_station_in_text(text)

        if base_stations:
            return base_stations.pole, base_stations

        pole = self._find_pole_in_text(text)
        if pole:
            return pole, None

        return None, None

    def find_pole_and_base_station_in_msg(
        self, msg: EmailMessage
    ) -> tuple[Optional[Pole], Optional[BaseStation]]:
        """Поиск Pole и BaseStation в теме или теле письма."""
        subject_text = msg.email_subject
        if subject_text:
            pole, base_station = (
                self.find_pole_and_base_station_in_text(subject_text)
            )
            if pole is not None:
                return pole, base_station

        body_text = msg.email_body
        if body_text:
            pole, base_station = (
                self.find_pole_and_base_station_in_text(body_text)
            )
            if pole is not None:
                return pole, base_station

        return None, None
