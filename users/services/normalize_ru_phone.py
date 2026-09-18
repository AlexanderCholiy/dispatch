import re


def normalize_ru_phone(value):
    """
    Приводит российский номер к единому виду: 8XXXXXXXXXX (11 цифр).

    79161234567      -> 89161234567
    +7 916 123-45-67 -> 89161234567
    8 (916) 123-45-67-> 89161234567
    89117607607      -> 89117607607 (без изменений)
    """

    if not value:
        return value

    digits = re.sub(r'\D', '', value)

    if digits.startswith('7') and len(digits) == 11:
        digits = '8' + digits[1:]

    print(digits)

    return digits
