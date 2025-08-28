import json
import re


def normalize_text_with_json(text: str) -> str:
    """
    Ищет JSON в тексте и преобразует его в человеко-читаемый формат.
    Если JSON невалидный – возвращает как есть.
    """
    json_pattern = re.compile(r'(\{.*?\}|\[.*?\])', re.DOTALL)

    def dict_to_pretty(data, indent: int = 0) -> str:
        """Рекурсивно преобразует dict/list в читаемый текст"""
        spaces = '  ' * indent
        if isinstance(data, dict):
            return '\n'.join(
                f'{spaces}{key}: {dict_to_pretty(value, indent + 1)}'
                for key, value in data.items()
            )
        elif isinstance(data, list):
            return '\n'.join(
                f'{spaces}- {dict_to_pretty(item, indent + 1)}'
                for item in data
            )
        else:
            return str(data)

    def pretty_json(match: re.Match) -> str:
        raw = match.group(0)
        try:
            parsed = json.loads(raw)
            return dict_to_pretty(parsed)
        except Exception:
            return raw

    return json_pattern.sub(pretty_json, text).strip()
