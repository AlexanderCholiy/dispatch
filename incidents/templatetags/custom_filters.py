from django import template

register = template.Library()


@register.filter
def dict_get(d: dict, key):
    """Возвращает значение словаря по ключу или пустую строку"""
    return d.get(key, '')
