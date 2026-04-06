from typing import Optional


def parse_gps_coordinate(value: str, is_latitude: bool) -> Optional[float]:
    """Парсит GPS координату из формата N5319.78106 в десятичные градусы."""

    if not value or not isinstance(value, str):
        return None

    value = value.strip().upper()

    direction = value[0]
    if direction not in ('N', 'S', 'E', 'W'):
        return None

    num_str = value[1:]

    if '.' not in num_str:
        return None

    parts = num_str.split('.')
    if len(parts) != 2:
        return None

    degrees_part = parts[0]
    minutes_part = parts[1]

    try:
        if is_latitude:
            if len(degrees_part) < 2:
                return None
            deg = int(degrees_part[:2])
            min_str = degrees_part[2:] + '.' + minutes_part
        else:
            if len(degrees_part) < 3:
                return None
            deg = int(degrees_part[:3])
            min_str = degrees_part[3:] + '.' + minutes_part

        minutes = float(min_str)

        if minutes >= 60:
            return None

        result = deg + (minutes / 60.0)

        if direction in ('S', 'W'):
            result = -result

        return result

    except ValueError:
        return None
