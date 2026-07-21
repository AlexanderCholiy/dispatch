from django.utils import timezone

from incidents.models import Incident
from max.constants import ALLOWED_INCIDENT_TYPES


def format_incident_message(incident: Incident) -> tuple[str, str]:
    """
    Формирует сообщение об инциденте в двух форматах: Markdown и Plain Text.

    Returns:
        tuple[str, str]: (markdown_text, plain_text)
    """

    # 1. Сбор данных
    incident_name = str(incident)
    incident_date = incident.incident_date

    # Данные опоры
    pole_code = incident.pole.pole
    lat = incident.pole.pole_latitude
    lon = incident.pole.pole_longtitude
    coords_str = (
        f'{lat}, {lon}'
        if lat is not None and lon is not None else 'Нет координат'
    )
    address = incident.pole.address or 'Нет адреса'

    # Тип и подтип
    type_name = incident.incident_type.name
    subtype_name = incident.incident_subtype.name

    # Эмодзи
    emoji = ALLOWED_INCIDENT_TYPES[type_name]

    # Базовая станция и операторы
    bs_name = None
    operators_list = []

    if incident.base_station:
        bs_name = incident.base_station.bs_name
        operators_qs = incident.base_station.operator.all()
        operators_list = sorted(
            list(
                set(
                    op.operator_name for op in operators_qs if op.operator_name
                )
            )
        )

    operators_str = ', '.join(operators_list)

    # Форматирование даты
    date_str = timezone.localtime(incident_date).strftime('%d.%m.%Y %H:%M')

    # --- ФОРМИРОВАНИЕ MARKDOWN ---
    summary_line = (
        f'Инцидент **{incident_name}** '
        f'зарегистрирован {date_str} (МСК).'
    )

    md_lines = [
        summary_line,
        '',
        f'{emoji} **{type_name} ({subtype_name})**.',
    ]

    md_lines.append('')

    if bs_name:
        md_lines.append(f'БС: **{bs_name}**')
        md_lines.append(f'Опора: **{pole_code}**')
        md_lines.append(f'Операторы: **{operators_str}**')
    else:
        md_lines.append(f'Опора: **{pole_code}**')

    md_lines.append('')
    md_lines.append(f'Координаты: _{coords_str}_')
    md_lines.append(f'Адрес: _{address}_')

    markdown_text = '\n'.join(md_lines)

    summary_line = (
        f'Инцидент {incident_name} '
        f'зарегистрирован {date_str} (МСК).'
    )
    pt_lines = [
        summary_line,
        '',
        f'{emoji} {type_name} ({subtype_name})',
    ]

    pt_lines.append('')

    if bs_name:
        pt_lines.append(f'БС: {bs_name}')
        pt_lines.append(f'Опора: {pole_code}')
        pt_lines.append(f'Операторы: {operators_str}')
    else:
        pt_lines.append(f'Опора: {pole_code}')

    pt_lines.append('')
    pt_lines.append(f'Координаты: {coords_str}')
    pt_lines.append(f'Адрес: {address}')

    plain_text = '\n'.join(pt_lines)

    return markdown_text, plain_text
