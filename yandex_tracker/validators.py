from typing import Optional
from logging import Logger
from datetime import datetime

from django.db import transaction, models
from dateutil import parser

from .utils import YandexTrackerManager
from incidents.models import Incident, IncidentType
from ts.models import Pole, BaseStation, AVRContractor, BaseStationOperator
from incidents.utils import IncidentManager
from ts.constants import UNDEFINED_CASE
from users.models import User, Roles


def check_yt_pole_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    type_of_incident_field: dict,
    incident: Incident,
) -> bool:
    pole_is_valid = True
    comment = None

    issue_key = issue['key']
    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id)
    status_key: str = issue['status']['key']

    type_of_incident_field_key = type_of_incident_field['id']
    type_of_incident: Optional[str] = issue.get(
        type_of_incident_field_key
    ) if type_of_incident_field_key else None

    if not pole_number:
        return pole_is_valid

    try:
        # Ищем опоры, которые начинаются с указанного шифра
        poles = Pole.objects.filter(pole__istartswith=pole_number)
        poles_count = poles.count()

        if poles_count == 0:
            raise Pole.DoesNotExist(
                f'Не найдено опор, начинающихся с "{pole_number}"')

        elif poles_count > 1:
            # Проверяем, есть ли точное совпадение среди найденных опор
            exact_match = poles.filter(pole=pole_number)
            if exact_match.exists():
                # Если есть точное совпадение - всё ок, используем его
                pass
            else:
                # Если точного совпадения нет, но есть похожие - это ошибка
                example_poles = list(poles.values_list('pole', flat=True)[:3])
                raise Pole.MultipleObjectsReturned(
                    f'Найдено {poles_count} опор, начинающихся с '
                    f'"{pole_number}". '
                    f'Примеры: {", ".join(example_poles)}. '
                    'Уточните шифр опоры.'
                )

    except (Pole.DoesNotExist, Pole.MultipleObjectsReturned) as e:
        pole_is_valid = False
        comment = str(e)

    if not pole_is_valid:
        yt_manager.update_incident_data(
            issue=issue,
            type_of_incident_field=type_of_incident_field,
            types_of_incident=type_of_incident,
            email_datetime=incident.incident_date,
            sla_deadline=incident.sla_deadline,
            is_sla_expired=yt_manager.get_sla_status(incident),
            pole_number=None,
            base_station_number=None,
            avr_name=None,
            operator_name=None,
        )
        if status_key != yt_manager.error_status_key:
            was_status_update = yt_manager.update_issue_status(
                issue_key,
                yt_manager.error_status_key,
                comment
            )
            if was_status_update:
                IncidentManager.add_error_status(incident, comment)

    return pole_is_valid


def check_yt_base_station_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    type_of_incident_field: dict,
    incident: Incident
) -> bool:
    base_station_is_valid = True
    comment = None
    error_exception = None

    issue_key = issue['key']
    base_station_number: Optional[str] = issue.get(
        yt_manager.base_station_global_field_id)
    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id)
    status_key: str = issue['status']['key']

    type_of_incident_field_key = (
        type_of_incident_field['id']) if type_of_incident_field else None
    type_of_incident: Optional[str] = issue.get(
        type_of_incident_field_key
    ) if type_of_incident_field_key else None

    if not base_station_number:
        return base_station_is_valid

    try:
        # Сначала проверяем точное совпадение, если указаны оба поля:
        if pole_number and base_station_number:
            try:
                exact_match = BaseStation.objects.get(
                    bs_name=base_station_number,
                    pole__pole=pole_number
                )
                # Если нашли точное совпадение - всё ок
                return base_station_is_valid
            except BaseStation.DoesNotExist:
                # Точного совпадения нет, продолжаем поиск по началу
                pass
            except BaseStation.MultipleObjectsReturned:
                # Несколько точных совпадений - тоже ок, используем первое
                exact_match = BaseStation.objects.filter(
                    bs_name=base_station_number,
                    pole__pole=pole_number
                ).first()
                return base_station_is_valid

        # Также проверяем точное совпадение только по БС (без опоры)
        if base_station_number:
            try:
                BaseStation.objects.get(
                    bs_name=base_station_number
                )
                # Если нашли точное совпадение только по БС - всё ок
                return base_station_is_valid
            except BaseStation.DoesNotExist:
                # Точного совпадения нет, продолжаем поиск по началу
                pass
            except BaseStation.MultipleObjectsReturned:
                # Несколько точных совпадений - тоже ок, используем первое
                BaseStation.objects.filter(
                    bs_name=base_station_number
                ).first()
                return base_station_is_valid

        # Оригинальная логика поиска по началу текста
        base_stations = BaseStation.objects.filter(
            bs_name__istartswith=base_station_number)
        base_stations_count = base_stations.count()

        if base_stations_count == 0:
            raise BaseStation.DoesNotExist(
                f'Не найдено БС, начинающихся с "{base_station_number}"')

        elif base_stations_count > 1:
            if pole_number:
                filtered_base_stations = base_stations.filter(
                    pole__pole__istartswith=pole_number)
                filtered_count = filtered_base_stations.count()

                if filtered_count == 0:
                    raise Pole.DoesNotExist(
                        f'Найдено {base_stations_count} базовых станций, '
                        f'начинающихся с "{base_station_number}", '
                        'но ни одна не привязана к опоре, начинающейся с '
                        f'"{pole_number}".'
                    )
                elif filtered_count > 1:
                    # Проверяем есть ли точное совпадение среди отфильтрованных
                    exact_match = filtered_base_stations.filter(
                        bs_name=base_station_number)
                    if exact_match.count() != 1:
                        example_stations = list(
                            filtered_base_stations
                            .values_list('bs_name', flat=True)[:3]
                        )
                        raise Pole.DoesNotExist(
                            f'Найдено {filtered_count} БС, начинающихся с '
                            f'"{base_station_number}" и привязанных к опорам, '
                            f'начинающимся с "{pole_number}". '
                            f'Примеры: {", ".join(example_stations)}. '
                            'Уточните название базовой станции.'
                        )
            else:
                example_stations = list(
                    base_stations.values_list('bs_name', flat=True)[:3])
                raise ValueError(
                    f'Найдено {base_stations_count} БС, начинающихся с '
                    f'"{base_station_number}". '
                    f'Примеры: {", ".join(example_stations)}. '
                    'Уточните шифр опоры.'
                )

        else:
            base_station = base_stations.first()
            if pole_number and base_station.pole:
                if not base_station.pole.pole.startswith(pole_number):
                    raise Pole.DoesNotExist(
                        f'Базовая станция "{base_station.bs_name}" привязана '
                        f'к опоре "{base_station.pole.pole}", '
                        f'а указана опора "{pole_number}"'
                    )

    except (BaseStation.DoesNotExist, Pole.DoesNotExist, ValueError) as e:
        base_station_is_valid = False
        comment = str(e)
        error_exception = e

    if not base_station_is_valid:
        yt_manager.update_incident_data(
            issue=issue,
            type_of_incident_field=type_of_incident_field,
            types_of_incident=type_of_incident,
            email_datetime=incident.incident_date,
            sla_deadline=incident.sla_deadline,
            is_sla_expired=yt_manager.get_sla_status(incident),
            pole_number=pole_number if not isinstance(
                error_exception, Pole.DoesNotExist) else None,
            base_station_number=None,
            avr_name=None,
            operator_name=None,
        )
        if status_key != yt_manager.error_status_key:
            was_status_update = yt_manager.update_issue_status(
                issue_key,
                yt_manager.error_status_key,
                comment
            )
            if was_status_update:
                IncidentManager.add_error_status(incident, comment)

    return base_station_is_valid


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
    yt_manager: YandexTrackerManager,
    issue: dict,
    yt_users: dict,
    incident: Incident,
) -> bool:
    user_is_valid = True
    user: Optional[dict] = issue.get('assignee')

    user_uid = int(user['id']) if user else None
    username: Optional[str] = next(
        (name for name, uid in yt_users.items() if uid == user_uid), None)
    users_in_db = User.objects.filter(role=Roles.DISPATCH, is_active=True)
    usernames_in_db = [usr.username for usr in users_in_db]

    if username and username not in usernames_in_db:
        user_is_valid = False

    return user_is_valid


def check_yt_type_of_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    type_of_incident_field: Optional[dict],
    incident: Incident,
) -> bool:
    type_of_incident_is_valid = True

    type_of_incident_field_key = (
        type_of_incident_field['id']) if type_of_incident_field else None
    type_of_incident: Optional[str] = issue.get(
        type_of_incident_field_key
    ) if type_of_incident_field_key else None
    type_of_incident_in_db = IncidentType.objects.all()
    valid_names_of_types = [tp.name for tp in type_of_incident_in_db]

    issue_key = issue['key']
    status_key: str = issue['status']['key']

    if (
        type_of_incident
        and type_of_incident not in valid_names_of_types
    ):
        type_of_incident_is_valid = False
        if status_key != yt_manager.error_status_key:
            comment = (
                f'Неверно указан тип инцидента ({type_of_incident}).'
                f'Допустимые значения: {", ".join(valid_names_of_types)}.'
            )
            was_status_update = yt_manager.update_issue_status(
                issue_key,
                yt_manager.error_status_key,
                comment
            )
            if was_status_update:
                IncidentManager.add_error_status(incident, comment)

    return type_of_incident_is_valid


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


def check_yt_deadline_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    type_of_incident_field: Optional[dict],
    incident: Incident,
) -> bool:
    is_valid_deadline_incident = True

    incident_deadline: Optional[str] = issue.get(
        yt_manager.sla_deadline_global_field_id)

    if incident_deadline:
        try:
            incident_deadline = parser.parse(incident_deadline)
        except ValueError:
            incident_deadline = None

    is_valid_type_of_incident = check_yt_type_of_incident(
        yt_manager, issue, type_of_incident_field, incident
    )

    if not is_valid_type_of_incident:
        is_valid_deadline_incident = False
    else:
        is_valid_deadline_incident = True if (
            incident_deadline == incident.sla_deadline) else False

    return is_valid_deadline_incident


def check_yt_expired_incident(
    yt_manager: YandexTrackerManager,
    issue: dict,
    incident: Incident,
) -> bool:
    is_valid_expired_incident = True

    incident_deadline: Optional[str] = issue.get(
        yt_manager.sla_deadline_global_field_id)

    sla_is_expired: Optional[str] = issue.get(
        yt_manager.is_sla_expired_global_field_id)

    if incident_deadline:
        try:
            incident_deadline: datetime = parser.parse(incident_deadline)
        except ValueError:
            incident_deadline = None

    if not sla_is_expired:
        is_valid_expired_incident = False
    else:
        expected_status = yt_manager.get_sla_status(incident)
        if sla_is_expired != expected_status:
            is_valid_expired_incident = False

    return is_valid_expired_incident


@transaction.atomic
def check_yt_incident_data(
    yt_manager: YandexTrackerManager,
    logger: Logger,
    issue: dict,
    yt_users: dict,
    type_of_incident_field: dict,
) -> Optional[bool]:
    """
    Проверка данных в YandexTracker.

    Returns:
        bool | None: Если данные по инциденту корректны вернем True, если нет
        False. Если заявка без YT_DATABASE_GLOBAL_FIELD_ID, тогда None.

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
    issue_key = issue['key']
    database_id: Optional[int] = issue[yt_manager.database_global_field_id]

    if not database_id:
        return None

    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id)
    base_station_number: Optional[str] = issue.get(
        yt_manager.base_station_global_field_id)
    status_key: str = issue['status']['key']
    user: Optional[dict] = issue.get('assignee')

    type_of_incident_field_key = type_of_incident_field['id']
    type_of_incident: Optional[str] = issue.get(type_of_incident_field_key)

    try:
        incident = Incident.objects.get(pk=database_id)
    except Incident.DoesNotExist:
        if status_key != yt_manager.error_status_key:
            comment = (
                f'Неизвестный {yt_manager.database_global_field_id} для '
                'внутреннего номера инцидента.'
            )
            was_status_update = yt_manager.update_issue_status(
                issue_key,
                yt_manager.error_status_key,
                comment
            )
            if was_status_update:
                logger.debug(comment)
        return False

    # Синхронизируем актуальность заявки в базе:
    if incident.is_incident_finish:
        incident.is_incident_finish = False
        incident.save()

    # Проверяем можно ли указанному диспетчеру назначать заявки:
    is_valid_user = check_yt_user_incident(
        yt_manager, issue, yt_users, incident)

    # Синхронизируем ответственного диспетчера в базе:
    if is_valid_user:
        user_uid = int(user['id']) if user else None
        username: Optional[str] = next(
            (name for name, uid in yt_users.items() if uid == user_uid), None)
        if incident.responsible_user and not username:
            incident.responsible_user = None
            incident.save()
        elif not incident.responsible_user and username:
            incident.responsible_user = User.objects.get(username=username)
            incident.save()

    # Проверяем, что тип инцидента соответствует одному из типов в базе:
    is_valid_type_of_incident = check_yt_type_of_incident(
        yt_manager, issue, type_of_incident_field, incident,
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

    # Проверка даты и времени регистрации инциденты:
    is_valid_incident_datetime = check_yt_datetime_incident(
        yt_manager, issue, incident)

    # Проверка дедлайна SLA:
    is_valid_incident_deadline = check_yt_deadline_incident(
        yt_manager, issue, type_of_incident_field, incident
    )

    # Проверка статуса SLA:
    is_valid_expired_incident = check_yt_expired_incident(
        yt_manager, issue, incident
    )

    # Синхронизируем данные по базовой станции (ДО проверки опоры):
    is_valid_base_station = check_yt_base_station_incident(
        yt_manager, issue, type_of_incident_field, incident)
    incident_bs = incident.base_station
    if not is_valid_base_station:
        logger.debug(f'Ошибка {issue_key}: неверный номер базовой станции.')
        return False

    # Синхронизируем БС и опору из БС
    if not incident_bs and base_station_number:
        exact_bs = BaseStation.objects.filter(
            bs_name=base_station_number).first()
        if exact_bs:
            incident.base_station = exact_bs
            # Если нашли БС, устанавливаем опору из БС
            if exact_bs.pole:
                incident.pole = exact_bs.pole
        else:
            bs_candidate = BaseStation.objects.filter(
                bs_name__istartswith=base_station_number
            ).order_by('bs_name').first()
            if bs_candidate:
                incident.base_station = bs_candidate
                # Если нашли БС, устанавливаем опору из БС
                if bs_candidate.pole:
                    incident.pole = bs_candidate.pole
        incident.save()

    elif incident_bs and not base_station_number:
        incident.base_station = None
        incident.save()

    elif incident_bs and base_station_number:
        if not incident_bs.bs_name.startswith(base_station_number):
            exact_bs = BaseStation.objects.filter(
                bs_name=base_station_number).first()
            if exact_bs:
                incident.base_station = exact_bs
                # Обновляем опору из новой БС
                if exact_bs.pole:
                    incident.pole = exact_bs.pole
            else:
                bs_candidate = BaseStation.objects.filter(
                    bs_name__istartswith=base_station_number
                ).order_by('bs_name').first()
                if bs_candidate:
                    incident.base_station = bs_candidate
                    # Обновляем опору из новой БС
                    if bs_candidate.pole:
                        incident.pole = bs_candidate.pole
            incident.save()

    # ОТДЕЛЬНАЯ ОБРАБОТКА: есть номер БС, но нет опоры
    if base_station_number and not incident.pole:
        # Пытаемся найти БС и взять опору из неё
        exact_bs = BaseStation.objects.filter(
            bs_name=base_station_number).first()
        if exact_bs and exact_bs.pole:
            incident.base_station = exact_bs
            incident.pole = exact_bs.pole
            incident.save()
        else:
            bs_candidate = BaseStation.objects.filter(
                bs_name__istartswith=base_station_number
            ).order_by('bs_name').first()
            if bs_candidate and bs_candidate.pole:
                incident.base_station = bs_candidate
                incident.pole = bs_candidate.pole
                incident.save()

    # ТЕПЕРЬ проверяем опору (после того как БС могла установить опору)
    is_valid_pole_number = check_yt_pole_incident(
        yt_manager, issue, type_of_incident_field, incident)
    incident_pole = incident.pole
    if not is_valid_pole_number:
        logger.debug(f'Ошибка {issue_key}: неверный шифр опоры.')
        return False

    # Синхронизируем данные по опоре (только если БС не установила опору)
    if not incident_pole and pole_number:
        exact_pole = Pole.objects.filter(pole=pole_number).first()
        if exact_pole:
            incident.pole = exact_pole
        else:
            incident.pole = Pole.objects.filter(
                pole__istartswith=pole_number
            ).order_by('pole').first()
        incident.save()

    elif incident_pole and not pole_number:
        # Удаляем опору только если она не от БС
        if (
            not incident.base_station
            or incident.base_station.pole != incident_pole
        ):
            incident.pole = None
            incident.save()

    elif incident_pole and pole_number:
        if not incident_pole.pole.startswith(pole_number):
            # Обновляем опору только если она не от БС
            if (
                not incident.base_station
                or incident.base_station.pole != incident_pole
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
        yt_manager, issue, incident)
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

    validation_errors = []
    checks = [
        (is_valid_avr_name, 'подрядчик по АВР'),
        (is_valid_operator_bs, 'оператор базовой станции'),
        (is_valid_incident_datetime, 'дата и время инцидента'),
        (is_valid_type_of_incident, 'тип инцидента'),
        (is_valid_incident_deadline, 'дедлайн SLA'),
        (is_valid_expired_incident, 'статус SLA'),
        (is_valid_pole_number, 'шифр опоры'),
        (is_valid_base_station, 'номер базовой станции'),
    ]

    for is_valid, error_text in checks:
        if not is_valid:
            validation_errors.append(error_text)

    if validation_errors:
        yt_manager.update_incident_data(
            issue=issue,
            type_of_incident_field=type_of_incident_field,
            types_of_incident=(
                incident.incident_type.name
            ) if incident.incident_type else None,
            email_datetime=incident.incident_date,
            sla_deadline=incident.sla_deadline,
            is_sla_expired=yt_manager.get_sla_status(incident),
            pole_number=incident.pole.pole if incident.pole else None,
            base_station_number=(
                incident.base_station.bs_name
            ) if incident.base_station else None,
            avr_name=avr.contractor_name if avr else None,
            operator_name=(
                ', '.join(op.operator_name for op in operator_bs)
            ) if operator_bs else None,
        )
        error_message = (
            'неверно указан'
            + ('ы: ' if len(validation_errors) > 1 else ' ')
            + ', '.join(validation_errors)
        )
        logger.debug(f'Ошибка {issue_key}: {error_message}')
        return False

    return True
