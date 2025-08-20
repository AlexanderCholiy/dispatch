import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class SocialValidators:
    """Валидаторы для почты и телефонов."""

    @staticmethod
    def normalize_phone(phone: str) -> str | None:
        """
        Нормализует телефон в формат 8XXXXXXXXXX.
        Возвращает None, если телефон невалидный.
        """
        if not phone:
            return None

        digits = re.sub(r'[^\d+]', '', phone)

        if digits.startswith('8') and len(digits) == 11:
            return digits

        if digits.startswith('+7') and len(digits) == 12:
            return '+7' + digits[1:]

        return None

    @staticmethod
    def split_and_validate_phones(
        phones_str: str
    ) -> tuple[list[str], list[str]]:
        """
        Разделяет строку на телефоны и валидирует каждый.
        Поддерживает разделители: ; , пробел.
        """
        raw_phones = re.split(r'[;,\s]+', phones_str.strip())

        valid_phones = []
        invalid_phones = []

        for phone in raw_phones:
            if not phone:
                continue
            normalized = SocialValidators.normalize_phone(phone)
            if normalized:
                valid_phones.append(normalized)
            else:
                invalid_phones.append(phone)

        return valid_phones, invalid_phones

    @staticmethod
    def split_and_validate_emails(
        emails_str: str
    ) -> tuple[list[str], list[str]]:
        """
        Разделяет строку на email-ы и валидирует каждый.
        Поддерживает разделители: ; , пробел.
        """
        raw_emails = re.split(r"[;,\s]+", emails_str.strip())

        valid_emails = []
        invalid_emails = []

        for email in raw_emails:
            if not email:
                continue
            try:
                validate_email(email)
                valid_emails.append(email)
            except ValidationError:
                invalid_emails.append(email)

        return valid_emails, invalid_emails
