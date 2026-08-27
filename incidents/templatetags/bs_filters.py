from django import template
from django.db.models import QuerySet

from ts.models import BaseStationOperator

register = template.Library()


@register.filter
def unique_groups(operators: QuerySet[BaseStationOperator]):
    """Уникальные группы (фолбек на имя), отсортированные, через запятую"""
    seen = set()
    result = []
    for op in operators:
        val = op.operator_group or op.operator_name
        if val and val not in seen:
            seen.add(val)
            result.append(val)
    return ', '.join(sorted(result))


@register.filter
def unique_names(operators: QuerySet[BaseStationOperator]):
    """Уникальные имена, отсортированные, через запятую"""
    seen = set()
    result = []
    for op in operators:
        name = op.operator_name
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return ', '.join(sorted(result))
