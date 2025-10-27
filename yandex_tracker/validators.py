import bisect
from datetime import datetime
from functools import partial
from logging import Logger
from typing import Callable, Optional, TypedDict

from dateutil import parser
from django.db import models, transaction
from django.utils import timezone

from incidents.constants import AVR_CATEGORY, MAX_FUTURE_END_DELTA
from incidents.models import (
    Incident,
    IncidentCategory,
    IncidentCategoryRelation,
    IncidentType,
)
from monitoring.models import DeviceStatus, DeviceType
from ts.constants import UNDEFINED_CASE
from ts.models import AVRContractor, BaseStation, BaseStationOperator, Pole
from users.models import User

from .constants import MAX_MONITORING_DEVICES
from .utils import YandexTrackerManager


class DevicesData(TypedDict):
    modem_ip: str
    pole_1__pole: str
    pole_2__pole: str | None
    pole_3__pole: str | None
    level: int
    status__id: int


def find_poles_by_prefix(
    pole_names_sorted: list[str], prefix: str
) -> list[str]:
    """
    Возвращает список опор, начинающихся с prefix, используя бинарный поиск.
    """
    start_index = bisect.bisect_left(pole_names_sorted, prefix)
    end_prefix = prefix[:-1] + chr(ord(prefix[-1]) + 1) if prefix else prefix
    end_index = bisect.bisect_left(pole_names_sorted, end_prefix)

    return pole_names_sorted[start_index:end_index]


def check_yt_pole_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    pole_names_sorted: list[str, Pole],
) -> tuple[bool, Optional[str]]:
    """
    Проверяет корректность шифра опоры в задаче Яндекс Трекера.

    Returns:
        (is_valid, message):
            - is_valid: bool — флаг корректности.
            - message: str — сообщение об ошибке или успехе.
    """
    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id
    )

    if not pole_number:
        return True, 'Шифр опоры не указан — проверка не требуется.'

    try:
        # Сначала точное совпадение (O(1) через бинарный поиск)
        idx = bisect.bisect_left(pole_names_sorted, pole_number)
        if (
            idx < len(pole_names_sorted)
            and pole_names_sorted[idx] == pole_number
        ):
            return True, f'Опора "{pole_number}" найдена точно.'

        # Если точного нет — ищем все по префиксу
        matching_names = find_poles_by_prefix(pole_names_sorted, pole_number)

        if not matching_names:
            raise Pole.DoesNotExist(
                f'Не найдено опор, начинающихся с "{pole_number}"'
            )

        elif len(matching_names) > 1:
            exact_matches = [p for p in matching_names if p == pole_number]
            if not exact_matches:
                example_poles = matching_names[:3]
                raise Pole.MultipleObjectsReturned(
                    f'Найдено {len(matching_names)} опор, начинающихся с '
                    f'"{pole_number}". Примеры: {", ".join(example_poles)}. '
                    'Уточните шифр опоры.'
                )

        return True, f'Опора "{pole_number}" найдена по префиксу.'

    except (Pole.DoesNotExist, Pole.MultipleObjectsReturned) as e:
        return False, str(e)


def check_yt_base_station_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    all_base_stations: dict[tuple[str, Optional[str]], BaseStation]
) -> tuple[bool, str]:
    """
    Проверяет корректность номера базовой станции и её соответствие опоре.

    Returns:
        (is_valid, message):
            - is_valid: bool — результат проверки.
            - message: str — описание результата (успех или ошибка).
    """
    base_station_number: Optional[str] = issue.get(
        yt_manager.base_station_global_field_id
    )
    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id
    )

    if not base_station_number:
        return True, 'Номер базовой станции не указан — проверка не требуется.'

    try:
        # Проверяем точное совпадение по ключу (номер БС + опора)
        bs_key = (base_station_number, pole_number)

        if bs_key in all_base_stations:
            return True, (
                f'Базовая станция "{base_station_number}"'
                + (f' (опора "{pole_number}")' if pole_number else '')
                + " найдена точно."
            )

        # Ищем все БС, которые начинаются с номера
        matching_stations = [
            bs for (bs_name, _), bs in all_base_stations.items()
            if bs_name.startswith(base_station_number)
        ]

        if pole_number:
            matching_stations = [
                bs for bs in matching_stations
                if bs.pole and bs.pole.pole.startswith(pole_number)
            ]

        if not matching_stations:
            raise ValueError((
                f'Не найдено БС, начинающихся с "{base_station_number}"'
                + (
                    f' и привязанных к опоре "{pole_number}"'
                ) if pole_number else ''
            ))

        if len(matching_stations) > 1:
            exact_matches = [
                bs for bs in matching_stations
                if (
                    bs.bs_name == base_station_number
                    and (
                        not pole_number
                        or (bs.pole and bs.pole.pole == pole_number)
                    )
                )
            ]

            if not exact_matches or len(exact_matches) > 1:
                example_stations = [
                    bs.bs_name for bs in matching_stations[:3]]
                examples_text = (
                    f'Примеры: {", ".join(example_stations)}. '
                    if example_stations else ''
                )

                raise ValueError(
                    f'Найдено {len(matching_stations)} БС, начинающихся '
                    f'с "{base_station_number}"'
                    + (
                        (
                            f' и привязанных к опоре "{pole_number}". '
                        ) if pole_number else '. '
                    )
                    + examples_text
                    + 'Уточните шифр опоры и номер БС.'
                )

        return True, (
            f'Базовая станция "{base_station_number}" '
            + (f'(опора "{pole_number}")' if pole_number else '')
            + ' найдена по префиксу.'
        )

    except ValueError as e:
        return False, str(e)


def check_yt_avr_incident(
    yt_manager: YandexTrackerManager, issue: dict, incident: Incident
) -> bool:
    avr_is_valid = True
    avr_name: Optional[str] = issue.get(yt_manager.avr_name_global_field_id)

    avr = (
        incident.pole.avr_contractor
        or AVRContractor.objects.get(contractor_name=UNDEFINED_CASE)
    ) if incident.pole else None

    if (
        (avr and not avr_name)
        or (avr and avr.contractor_name != avr_name)
        or (not avr and avr_name)
    ):
        avr_is_valid = False

    return avr_is_valid


def check_yt_operator_bs_incident(
    yt_manager: YandexTrackerManager, issue: dict, incident: Incident
) -> bool:
    operator_bs_is_valid = True
    operator_name: Optional[str] = issue.get(
        yt_manager.operator_name_global_field_name)

    # Связь m2m:
    operator_bs = None
    if incident.base_station and incident.base_station.operator.exists():
        operator_bs: models.QuerySet[BaseStationOperator] = (
            incident.base_station.operator.all())

    if (
        (operator_bs and not operator_name)
        or (
            operator_bs
            and ', '.join(
                op.operator_name for op in operator_bs
            ) != operator_name
        )
        or (not operator_bs and operator_name)
    ):
        operator_bs_is_valid = False

    return operator_bs_is_valid


def check_yt_user_incident(
    issue: dict,
    yt_users: dict,
    usernames_in_db: list[str],
) -> bool:
    user_is_valid = True
    user: Optional[dict] = issue.get('assignee')

    user_uid = int(user['id']) if user else None
    username: Optional[str] = next(
        (name for name, uid in yt_users.items() if uid == user_uid), None
    )

    if username and username not in usernames_in_db:
        user_is_valid = False

    return user_is_valid


def check_yt_type_of_incident(
    issue: dict,
    type_of_incident_field: Optional[dict],
    valid_names_of_types: list[str],
) -> tuple[bool, str]:
    """
    Проверяет корректность типа инцидента в задаче Yandex Tracker.

    Returns:
        (is_valid, message):
            - is_valid: bool — результат проверки.
            - message: str — описание результата (успех или ошибка).
    """
    type_of_incident_field_key = (
        type_of_incident_field['id']) if type_of_incident_field else None
    type_of_incident: Optional[str] = issue.get(
        type_of_incident_field_key
    ) if type_of_incident_field_key else None

    if not type_of_incident:
        return True, 'Тип инцидента не указан — проверка не требуется.'

    if (
        type_of_incident
        and type_of_incident not in valid_names_of_types
    ):
        return False, (
            f'Неверно указан тип инцидента ({type_of_incident}).'
            f'Допустимые значения: {", ".join(valid_names_of_types)}.'
        )

    return True, f'Тип инцидента "{type_of_incident}" валиден.'


def check_yt_category(
    issue: dict,
    category_field: Optional[dict],
    valid_names_of_category: list[str],
) -> tuple[bool, str]:
    """
    Проверяет корректность категории инцидента в задаче Yandex Tracker.

    Returns:
        (is_valid, message):
            - is_valid: bool — результат проверки.
            - message: str — описание результата (успех или ошибка).
    """
    category_field_key = (
        category_field['id']) if category_field else None
    category: Optional[list[str]] = issue.get(
        category_field_key
    ) if category_field_key else None

    if not category:
        return True, 'Выставляем значение по умолчанию'

    if (
        category
        and not set(category).issubset(valid_names_of_category)
    ):
        return False, (
            f'Неверно указана категория инцидента ({', '.join(category)}). '
            f'Допустимые значения: {", ".join(valid_names_of_category)}.'
        )

    return True, 'Категории инцидента валидны.'


def check_yt_datetime_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
) -> bool:
    incident_datetime_is_valid = True

    email_datetime: Optional[str] = issue.get(
        yt_manager.email_datetime_global_field_id)

    if email_datetime:
        try:
            email_datetime = parser.parse(email_datetime)
            incident_datetime_is_valid = True if (
                incident.incident_date == email_datetime) else False
        except ValueError:
            incident_datetime_is_valid = False
    else:
        incident_datetime_is_valid = False

    return incident_datetime_is_valid


def _check_dates_consistency(
    incident: Incident,
    tracker_start_date: Optional[str],
    tracker_end_date: Optional[str],
    db_start_date: Optional[datetime],
    db_end_date: Optional[datetime],
) -> bool:
    """
    Проверка согласованности дат между трекером и БД.

    Args:
        tracker_start_date: Дата начала из трекера (строка)
        tracker_end_date: Дата окончания из трекера (строка)
        db_start_date: Дата начала из БД
        db_end_date: Дата окончания из БД

    Returns:
        bool: True если даты согласованы
    """
    try:
        parsed_start = parser.parse(
            tracker_start_date
        ) if tracker_start_date else None
    except (ValueError, TypeError):
        parsed_start = None

    try:
        parsed_end = parser.parse(
            tracker_end_date
        ) if tracker_end_date else None
    except (ValueError, TypeError):
        parsed_end = None

    if (
        (parsed_start and parsed_end and parsed_start > parsed_end)
        or (
            parsed_start
            and not parsed_end
            and db_end_date
            and parsed_start > db_end_date
        )
        or (
            parsed_end
            and not parsed_start
            and db_start_date
            and parsed_end < db_start_date
        )
    ):
        return False

    now = timezone.now()
    max_future_date = now + MAX_FUTURE_END_DELTA
    min_allowed_date = min(incident.insert_date, incident.incident_date)

    if parsed_start and min_allowed_date and parsed_start < min_allowed_date:
        return False

    if parsed_end and parsed_end > max_future_date:
        return False

    # Защита от автоматического перезаписывания - если в БД есть дата,
    # а в трекере нет:
    if (
        (not parsed_start and db_start_date)
        or (not parsed_end and db_end_date)
    ):
        return False

    return True


def check_avr_dates(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
) -> bool:
    return _check_dates_consistency(
        incident=incident,
        tracker_start_date=issue.get(
            yt_manager.avr_start_date_global_field_id
        ),
        tracker_end_date=issue.get(yt_manager.avr_end_date_global_field_id),
        db_start_date=incident.avr_start_date,
        db_end_date=incident.avr_end_date
    )


def check_rvr_dates(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
) -> bool:
    return _check_dates_consistency(
        incident=incident,
        tracker_start_date=issue.get(
            yt_manager.rvr_start_date_global_field_id
        ),
        tracker_end_date=issue.get(yt_manager.rvr_end_date_global_field_id),
        db_start_date=incident.rvr_start_date,
        db_end_date=incident.rvr_end_date
    )


def check_yt_avr_deadline_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    type_of_incident_field: Optional[dict],
    incident: Incident,
    valid_names_of_types: list[str],
) -> bool:
    avr_incident_deadline: Optional[str] = issue.get(
        yt_manager.sla_avr_deadline_global_field_id
    )

    try:
        avr_incident_deadline = parser.parse(
            avr_incident_deadline
        ) if avr_incident_deadline else None
    except ValueError:
        avr_incident_deadline = None

    is_valid_type_of_incident, _ = check_yt_type_of_incident(
        issue,
        type_of_incident_field,
        valid_names_of_types,
    )

    if not is_valid_type_of_incident:
        return False

    if avr_incident_deadline != incident.sla_avr_deadline:
        return False

    return True


def check_yt_rvr_deadline_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
) -> bool:
    is_valid_rvr_deadline_incident = True

    rvr_incident_deadline: Optional[str] = issue.get(
        yt_manager.sla_rvr_deadline_global_field_id)

    try:
        rvr_incident_deadline = parser.parse(
            rvr_incident_deadline
        ) if rvr_incident_deadline else None
    except ValueError:
        rvr_incident_deadline = None

    is_valid_rvr_deadline_incident = True if (
        rvr_incident_deadline == incident.sla_rvr_deadline
    ) else False

    return is_valid_rvr_deadline_incident


def check_yt_avr_expired_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
) -> bool:
    is_valid_avr_expired_incident = True

    sla_avr_is_expired: Optional[str] = issue.get(
        yt_manager.is_sla_avr_expired_global_field_id)

    if not sla_avr_is_expired:
        is_valid_avr_expired_incident = False
    else:
        expected_status = yt_manager.get_sla_avr_status(incident)
        if sla_avr_is_expired != expected_status:
            is_valid_avr_expired_incident = False

    return is_valid_avr_expired_incident


def check_yt_rvr_expired_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
) -> bool:
    is_valid_rvr_expired_incident = True

    sla_rvr_is_expired: Optional[str] = issue.get(
        yt_manager.is_sla_rvr_expired_global_field_id)

    if not sla_rvr_is_expired:
        is_valid_rvr_expired_incident = False
    else:
        expected_status = yt_manager.get_sla_rvr_status(incident)
        if sla_rvr_is_expired != expected_status:
            is_valid_rvr_expired_incident = False

    return is_valid_rvr_expired_incident


def prepare_monitoring_text(
    devices: Optional[list[DevicesData]]
) -> Optional[str]:
    """Формирует текстовую сводку по оборудованию мониторинга."""
    if not devices:
        return

    status_emojis = {
        'NORMAL': '🟩',
        'CRITICAL': '🟥',
        'MAJOR': '🟧',
        'MINOR': '🟨',
        'WARNING': '🟦',
        'UNMONITORED': '🟥',
        'TERMINATED': '🟥',
        'BLOCKED': '⬛️',
    }

    sorted_devices = sorted(
        devices,
        key=lambda d: (
            -d['level'], d['modem_ip'].strip() if d['modem_ip'] else ''
        )
    )[:MAX_MONITORING_DEVICES]

    # Длина колонок (с учетом отступов (не четное число))
    column_1_width = max([len(choice.label) for choice in DeviceType]) + 31
    column_2_width = max([len(choice.label) for choice in DeviceStatus])

    column_1_name = 'Тип устройства'
    column_2_name = 'Статус'

    # # Заголовок
    column_1_display = column_1_name.ljust(
        max(column_1_width - len(column_1_name), 0)
    )
    column_2_display = column_2_name.ljust(
        max(column_2_width - len(column_2_name), 0)
    )

    header = f'{column_1_display}\t{column_2_display}'
    spacer = '=' * (len(header) - 5)
    lines = [header, spacer]

    for dev in sorted_devices:
        level_display = DeviceType(
            dev.get('level')
        ).label if dev.get('level') is not None else 'UNKNOWN'
        level_aligned = level_display.ljust(
            max(column_1_width - len(level_display) - 8, 0)
        )

        status_display = DeviceStatus(
            dev.get('status__id')
        ).label if dev.get('status__id') is not None else 'UNKNOWN'
        emoji = status_emojis.get(status_display, '⬜️')
        status_text = f'{emoji} {status_display}'
        status_aligned = status_text.ljust(
            max(column_2_width - len(status_text), 0)
        )

        line = f'{level_aligned}\t{status_aligned}'
        lines.append(line)

    return '\n'.join(lines)


def check_yt_monitoring(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
    devices: dict[str, list[DevicesData]]
) -> bool:
    is_valid_yt_monitoring = True

    incident_monitoring: Optional[str] = issue.get(
        yt_manager.monitoring_global_field_id
    )

    if incident_monitoring and not incident.pole:
        return False

    if not incident_monitoring and not incident.pole:
        return True

    monitoring_devices = devices.get(incident.pole.pole)

    if incident_monitoring and not monitoring_devices:
        return False

    if not incident_monitoring and monitoring_devices:
        return False

    if not incident_monitoring and not monitoring_devices:
        return True

    if incident_monitoring != prepare_monitoring_text(
        devices.get(incident.pole.pole)
    ):
        return False

    return is_valid_yt_monitoring


@transaction.atomic
def check_yt_incident_data(
    incident: Incident,
    yt_manager: YandexTrackerManager,
    logger: Logger,
    issue: dict,
    yt_users: dict,
    type_of_incident_field: dict,
    valid_names_of_types: list[str],
    category_field: dict,
    valid_names_of_categories: list[str],
    usernames_in_db: list[str],
    pole_names_sorted: list[str, Pole],
    all_base_stations: dict[tuple[str, Optional[str]], BaseStation],
    devices_by_pole: dict[str, list[DevicesData]],
) -> tuple[bool, Optional[Callable], Optional[Callable]]:
    """
    Проверка данных в YandexTracker.

    Returns:
        (
            is_valid: bool,
            update_incident_data_func: Optional[Callable],
            update_issue_status_func: Optional[Callable]
        )

    Особенности:
        - Установить инциденту is_incident_finish=False.
        - Шифр опоры и номер базовой станции в БД и YandexTracker должны
        совпадать.
            - Если эти данные отсутствуют в БД, а в YandexTracker есть,
            тогда проверяем их и если всё в порядке, вносим в БД.
            - Если они отсутсвут в YandexTracker, а в БД есть, тогда удаляем
            эту запись из БД (опора была найдена не верно и диспетчер её
            убрал).
        - Имя оператора и подрядчика по АВР всегда берем из БД.
        - Если установлен известный тип инцидента, выставим дедлайн SLA.
    """
    update_incident_data_func = None
    update_issue_status_func = None

    issue_key = issue['key']
    status_key: str = issue['status']['key']

    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id)
    base_station_number: Optional[str] = issue.get(
        yt_manager.base_station_global_field_id)
    user: Optional[dict] = issue.get('assignee')

    type_of_incident_field_key = type_of_incident_field['id']
    type_of_incident: Optional[str] = issue.get(type_of_incident_field_key)

    category_field_key = category_field['id']
    category: Optional[list[str]] = issue.get(category_field_key)

    # Синхронизируем актуальность заявки в базе, код заявки:
    if incident.is_incident_finish or incident.code != issue_key:
        incident.is_incident_finish = False
        incident.code = issue_key
        incident.save()

    # Проверяем можно ли указанному диспетчеру назначать заявки:
    is_valid_user = check_yt_user_incident(
        issue, yt_users, usernames_in_db
    )

    # Синхронизируем ответственного диспетчера в базе:
    if is_valid_user:
        user_uid = int(user['id']) if user else None
        username: Optional[str] = next(
            (name for name, uid in yt_users.items() if uid == user_uid), None
        )

        if incident.responsible_user and not username:
            incident.responsible_user = None
            incident.save()
        elif not incident.responsible_user and username:
            incident.responsible_user = User.objects.get(username=username)
            incident.save()
        elif (
            incident.responsible_user
            and username
            and username != incident.responsible_user.username
        ):
            incident.responsible_user = User.objects.get(username=username)
            incident.save()

    # Проверяем, что тип инцидента соответствует одному из типов в базе:
    is_valid_type_of_incident, incident_comment = check_yt_type_of_incident(
        issue,
        type_of_incident_field,
        valid_names_of_types,
    )

    # Синхронизируем тип инцидента в базе:
    if is_valid_type_of_incident:
        if type_of_incident:
            if (
                (
                    incident.incident_type
                    and incident.incident_type.name != type_of_incident
                )
                or not incident.incident_type
            ):
                incident.incident_type = IncidentType.objects.get(
                    name=type_of_incident)
                incident.save()
        elif incident.incident_type:
            incident.incident_type = None
            incident.save()
    elif (
        not is_valid_type_of_incident
        and status_key != yt_manager.error_status_key
    ):
        update_issue_status_func = partial(
            yt_manager.update_issue_status,
            issue_key,
            yt_manager.error_status_key,
            incident_comment
        )

    # Проверка, что категория валидна и если ничего не выбрано то АВР:
    is_valid_category, incident_comment = check_yt_category(
        issue, category_field, valid_names_of_categories
    )

    # Синхронизируем категорию инцидента в базе:
    if is_valid_category:
        if category:
            current_categories = [
                cat.name for cat in incident.categories.all()
            ]

            if set(category) != set(current_categories):
                cat_2_del = (
                    set(current_categories) - set(category)
                )
                IncidentCategoryRelation.objects.filter(
                    incident=incident,
                    category__name__in=cat_2_del
                ).delete()

                for cat in category:
                    inc_cat, _ = IncidentCategory.objects.get_or_create(
                        name=cat
                    )
                    IncidentCategoryRelation.objects.get_or_create(
                        incident=incident,
                        category=inc_cat
                    )
        else:
            # Выставляем значение по умолчанию:
            inc_cat, _ = IncidentCategory.objects.get_or_create(
                name=AVR_CATEGORY
            )
            IncidentCategoryRelation.objects.get_or_create(
                incident=incident,
                category=inc_cat
            )
            update_incident_data_func = partial(
                yt_manager.update_incident_data,
                issue=issue,
                type_of_incident_field=type_of_incident_field,
                types_of_incident=type_of_incident,
                category_field=category_field,
                category=[AVR_CATEGORY],
                email_datetime=incident.incident_date,
                sla_avr_deadline=incident.sla_avr_deadline,
                is_sla_avr_expired=yt_manager.get_sla_avr_status(incident),
                avr_start_date=incident.avr_start_date,
                avr_end_date=incident.avr_end_date,
                sla_rvr_deadline=incident.sla_rvr_deadline,
                is_sla_rvr_expired=yt_manager.get_sla_rvr_status(incident),
                rvr_start_date=incident.rvr_start_date,
                rvr_end_date=incident.rvr_end_date,
                pole_number=pole_number,
                base_station_number=base_station_number,
                avr_name=issue.get(yt_manager.avr_name_global_field_id),
                operator_name=issue.get(
                    yt_manager.operator_name_global_field_name
                ),
                monitoring_data=issue.get(
                    yt_manager.monitoring_global_field_id
                )
            )

            logger.debug(
                f'Ошибка {issue_key}: не указана ни одна категория инцидента.'
            )

            return False, update_incident_data_func, update_issue_status_func
    elif (
        not is_valid_category
        and status_key != yt_manager.error_status_key
    ):
        update_issue_status_func = partial(
            yt_manager.update_issue_status,
            issue_key,
            yt_manager.error_status_key,
            incident_comment
        )

    # Проверка даты и времени регистрации инциденты:
    is_valid_incident_datetime = check_yt_datetime_incident(
        yt_manager, issue, incident)

    # Проверка дедлайна SLA (АВР):
    is_valid_avr_incident_deadline = check_yt_avr_deadline_incident(
        yt_manager,
        issue,
        type_of_incident_field,
        incident,
        valid_names_of_types,
    )

    # Проверка статуса SLA (АВР):
    is_valid_avr_expired_incident = check_yt_avr_expired_incident(
        yt_manager, issue, incident
    )

    # Проверка дедлайна SLA (РВР):
    is_valid_rvr_incident_deadline = check_yt_rvr_deadline_incident(
        yt_manager, issue, incident
    )

    # Проверка статуса SLA (РВР):
    is_valid_rvr_expired_incident = check_yt_rvr_expired_incident(
        yt_manager, issue, incident
    )

    # Синхронизируем дату и время SLA АВР:
    is_valid_avr_dates = check_avr_dates(yt_manager, issue, incident)
    if is_valid_avr_dates:
        avr_start_date: Optional[str] = issue.get(
            yt_manager.avr_start_date_global_field_id
        )
        avr_end_date: Optional[str] = issue.get(
            yt_manager.avr_end_date_global_field_id
        )

        try:
            avr_start_date = parser.parse(
                avr_start_date
            ) if avr_start_date else None
        except ValueError:
            avr_start_date = None

        try:
            avr_end_date = parser.parse(
                avr_end_date
            ) if avr_end_date else None
        except ValueError:
            avr_end_date = None

        was_avr_date_update = False

        if incident.avr_start_date != avr_start_date:
            incident.avr_start_date = avr_start_date
            was_avr_date_update = True

        if incident.avr_end_date != avr_end_date:
            incident.avr_end_date = avr_end_date
            was_avr_date_update = True

        if was_avr_date_update:
            incident.save()

    # Синхронизируем дату и время SLA РВР:
    is_valid_rvr_dates = check_rvr_dates(yt_manager, issue, incident)
    if is_valid_rvr_dates:
        rvr_start_date: Optional[str] = issue.get(
            yt_manager.rvr_start_date_global_field_id
        )
        rvr_end_date: Optional[str] = issue.get(
            yt_manager.rvr_end_date_global_field_id
        )

        try:
            rvr_start_date = parser.parse(
                rvr_start_date
            ) if rvr_start_date else None
        except ValueError:
            rvr_start_date = None

        try:
            rvr_end_date = parser.parse(rvr_end_date) if rvr_end_date else None
        except ValueError:
            rvr_end_date = None

        was_rvr_date_update = False

        if incident.rvr_start_date != rvr_start_date:
            incident.rvr_start_date = rvr_start_date
            was_rvr_date_update = True

        if incident.rvr_end_date != rvr_end_date:
            incident.rvr_end_date = rvr_end_date
            was_rvr_date_update = True

        if was_rvr_date_update:
            incident.save()

    # Синхронизируем данные по базовой станции (ДО проверки опоры):
    is_valid_base_station, bs_comment = check_yt_base_station_incident(
        yt_manager, issue, all_base_stations
    )
    incident_bs = incident.base_station
    if not is_valid_base_station:
        update_incident_data_func = partial(
            yt_manager.update_incident_data,
            issue=issue,
            type_of_incident_field=type_of_incident_field,
            types_of_incident=type_of_incident,
            category_field=category_field,
            category=category,
            email_datetime=incident.incident_date,
            sla_avr_deadline=incident.sla_avr_deadline,
            is_sla_avr_expired=yt_manager.get_sla_avr_status(incident),
            avr_start_date=incident.avr_start_date,
            avr_end_date=incident.avr_end_date,
            sla_rvr_deadline=incident.sla_rvr_deadline,
            is_sla_rvr_expired=yt_manager.get_sla_rvr_status(incident),
            rvr_start_date=incident.rvr_start_date,
            rvr_end_date=incident.rvr_end_date,
            pole_number=pole_number,
            base_station_number=None,
            avr_name=issue.get(yt_manager.avr_name_global_field_id),
            operator_name=None,
            monitoring_data=issue.get(yt_manager.monitoring_global_field_id)
        )
        if status_key != yt_manager.error_status_key:
            update_issue_status_func = partial(
                yt_manager.update_issue_status,
                issue_key,
                yt_manager.error_status_key,
                bs_comment
            )

        logger.debug(f'Ошибка {issue_key}: неверный номер базовой станции.')

        return False, update_incident_data_func, update_issue_status_func

    # Синхронизируем БС и опору из БС
    if base_station_number:
        bs_key = (base_station_number, pole_number)
        incident_bs_candidate = all_base_stations.get(bs_key)

        if not incident_bs_candidate:
            matching_stations = [
                bs
                for (bs_name, bs_pole_number), bs in all_base_stations.items()
                if bs_name.startswith(base_station_number)
                and (
                    pole_number is None
                    or (
                        bs_pole_number
                        and bs_pole_number.startswith(pole_number)
                    )
                )
            ]
            # Берём первую подходящую БС:
            incident_bs_candidate = (
                matching_stations[0]) if matching_stations else None

        # Устанавливаем БС и опору из найденного кандидата
        if incident_bs_candidate:
            bs_changed = incident.base_station != incident_bs_candidate
            pole_changed = (
                incident_bs_candidate.pole
                and incident.pole != incident_bs_candidate.pole
            )

            if bs_changed or pole_changed:
                incident.base_station = incident_bs_candidate
                incident.pole = incident_bs_candidate.pole
                incident.save()
        else:
            if incident.base_station is not None:
                incident.base_station = None
                incident.save()

    elif incident_bs and not base_station_number:
        incident.base_station = None
        incident.save()

    # ТЕПЕРЬ проверяем опору (после того как БС могла установить опору)
    is_valid_pole_number, pole_comment = check_yt_pole_incident(
        yt_manager, issue, pole_names_sorted
    )
    if not is_valid_pole_number:
        update_incident_data_func = partial(
            yt_manager.update_incident_data,
            issue=issue,
            type_of_incident_field=type_of_incident_field,
            types_of_incident=type_of_incident,
            category_field=category_field,
            category=category,
            email_datetime=incident.incident_date,
            sla_avr_deadline=incident.sla_avr_deadline,
            is_sla_avr_expired=yt_manager.get_sla_avr_status(incident),
            avr_start_date=incident.avr_start_date,
            avr_end_date=incident.avr_end_date,
            sla_rvr_deadline=incident.sla_rvr_deadline,
            is_sla_rvr_expired=yt_manager.get_sla_rvr_status(incident),
            rvr_start_date=incident.rvr_start_date,
            rvr_end_date=incident.rvr_end_date,
            pole_number=None,
            base_station_number=None,
            avr_name=None,
            operator_name=None,
            monitoring_data=None,
        )

        if status_key != yt_manager.error_status_key:
            update_issue_status_func = partial(
                yt_manager.update_issue_status,
                issue_key,
                yt_manager.error_status_key,
                pole_comment
            )

        logger.debug(f'Ошибка {issue_key}: неверный шифр опоры.')

        return False, update_incident_data_func, update_issue_status_func

    # Синхронизируем данные по опоре (только если БС не установила опору)
    if not incident.pole and pole_number:
        exact_pole = Pole.objects.filter(pole=pole_number).first()
        if exact_pole:
            incident.pole = exact_pole
        else:
            incident.pole = Pole.objects.filter(
                pole__istartswith=pole_number
            ).order_by('pole').first()
        incident.save()

    elif incident.pole and not pole_number:
        # Удаляем опору только если она не от БС
        if (
            not incident.base_station
            or incident.base_station.pole != incident.pole
        ):
            incident.pole = None
            incident.save()

    elif incident.pole and pole_number:
        if not incident.pole.pole.startswith(pole_number):
            # Обновляем опору только если она не от БС
            if (
                not incident.base_station
                or incident.base_station.pole != incident.pole
            ):
                exact_pole = Pole.objects.filter(pole=pole_number).first()
                if exact_pole:
                    incident.pole = exact_pole
                else:
                    incident.pole = Pole.objects.filter(
                        pole__istartswith=pole_number
                    ).order_by('pole').first()
                incident.save()

    # Синхронизируем данные оператора базовой станции:
    is_valid_avr_name = check_yt_avr_incident(yt_manager, issue, incident)
    avr = (
        incident.pole.avr_contractor
        or AVRContractor.objects.get(contractor_name=UNDEFINED_CASE)
    ) if incident.pole else None

    # Синхронизируем данные подрядчика по АВР:
    is_valid_operator_bs = check_yt_operator_bs_incident(
        yt_manager, issue, incident
    )
    # Связь m2m:
    operator_bs = None
    if incident.base_station and incident.base_station.operator.exists():
        operator_bs: models.QuerySet[BaseStationOperator] = (
            incident.base_station.operator.all())

    # Проверяем, что в трекере указан точный шифр опоры и номер базовой станции
    if is_valid_pole_number and incident.pole:
        is_valid_pole_number = pole_number == incident.pole.pole
    elif is_valid_pole_number and not incident.pole:
        is_valid_pole_number = pole_number is None

    if is_valid_pole_number and incident.base_station:
        is_valid_pole_number = base_station_number == (
            incident.base_station.bs_name)
    elif is_valid_pole_number and not incident.base_station:
        is_valid_pole_number = base_station_number is None

    # Проверяем, что статус оборудования в трекере совпадает с мониторингом
    is_valid_monitoring_data = check_yt_monitoring(
        yt_manager, issue, incident, devices_by_pole
    )

    validation_errors = []
    checks = [
        (is_valid_avr_name, 'подрядчик по АВР'),
        (is_valid_operator_bs, 'оператор базовой станции'),
        (is_valid_incident_datetime, 'дата и время инцидента'),
        (is_valid_type_of_incident, 'тип инцидента'),
        (is_valid_category, 'категория инцидента'),
        (is_valid_avr_incident_deadline, 'дедлайн SLA АВР'),
        (is_valid_avr_expired_incident, 'статус SLA АВР'),
        (is_valid_rvr_incident_deadline, 'дедлайн SLA РВР'),
        (is_valid_rvr_expired_incident, 'статус SLA РВР'),
        (is_valid_avr_dates, 'дата начала и конца АВР'),
        (is_valid_rvr_dates, 'дата начала и конца РВР'),
        (is_valid_pole_number, 'шифр опоры'),
        (is_valid_base_station, 'номер базовой станции'),
        (is_valid_monitoring_data, 'данные мониторинга'),
    ]

    for is_valid, error_text in checks:
        if not is_valid:
            validation_errors.append(error_text)

    if validation_errors:
        update_incident_data_func = partial(
            yt_manager.update_incident_data,
            issue=issue,
            type_of_incident_field=type_of_incident_field,
            types_of_incident=(
                incident.incident_type.name
            ) if incident.incident_type else None,
            category_field=category_field,
            category=category if is_valid_category else [AVR_CATEGORY],
            email_datetime=incident.incident_date,
            sla_avr_deadline=incident.sla_avr_deadline,
            is_sla_avr_expired=yt_manager.get_sla_avr_status(incident),
            avr_start_date=incident.avr_start_date,
            avr_end_date=incident.avr_end_date,
            sla_rvr_deadline=incident.sla_rvr_deadline,
            is_sla_rvr_expired=yt_manager.get_sla_rvr_status(incident),
            rvr_start_date=incident.rvr_start_date,
            rvr_end_date=incident.rvr_end_date,
            pole_number=incident.pole.pole if incident.pole else None,
            base_station_number=(
                incident.base_station.bs_name
            ) if incident.base_station else None,
            avr_name=avr.contractor_name if avr else None,
            operator_name=(
                ', '.join(op.operator_name for op in operator_bs)
            ) if operator_bs else None,
            monitoring_data=(
                prepare_monitoring_text(
                    devices_by_pole.get(incident.pole.pole)
                )
                if incident.pole else None
            )
        )

        error_message = (
            'необходимо обновить: '
            + ', '.join(validation_errors)
        )

        logger.debug(f'Ошибка {issue_key}: {error_message}')

        return False, update_incident_data_func, update_issue_status_func

    return True, update_incident_data_func, update_issue_status_func
