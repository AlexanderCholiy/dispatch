from django.core.validators import RegexValidator

mac_validator = RegexValidator(
    regex=r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
    message=(
        'Введите корректный MAC-адрес '
        '(например, AA:BB:CC:DD:EE:FF или AA-BB-CC-DD-EE-FF)'
    )
)
