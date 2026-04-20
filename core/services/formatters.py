from datetime import timedelta


def truncate_text(
    text: str, max_length: int = 30, suffix: str = '...'
) -> str:
    if not text:
        return ''

    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def format_timedelta_readable(
    td: timedelta, high_precision: bool = False
) -> str:
    total_seconds = int(td.total_seconds())
    milliseconds = td.microseconds // 1000

    days = total_seconds // 86400
    remaining = total_seconds % 86400
    hours = remaining // 3600
    remaining %= 3600
    minutes = remaining // 60
    seconds = remaining % 60

    units = [
        ('дн.', days),
        ('ч.', hours),
        ('мин.', minutes),
        ('сек.', seconds),
        ('мс.', milliseconds),
    ]

    first_idx = next((i for i, (_, v) in enumerate(units) if v > 0), None)

    if first_idx is None:
        return '0 сек.'

    if high_precision:
        limit = len(units) - 1
    else:
        limits = {0: 2, 1: 2, 2: 3, 3: 4}
        limit = limits.get(first_idx, 4)

    parts = []
    for idx, (unit_name, value) in enumerate(units):
        if value == 0:
            continue
        if idx > limit:
            break

        parts.append(f'{value} {unit_name}')

    return ' '.join(parts) if parts else '0 сек.'
