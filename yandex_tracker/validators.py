import json
import re
from typing import Optional
from logging import Logger

from django.db import transaction, models

from .utils import YandexTrackerManager
from incidents.models import Incident
from ts.models import Pole, BaseStation, AVRContractor, BaseStationOperator
from incidents.utils import IncidentManager
from ts.constants import UNDEFINED_CASE


def check_yt_pole_incident(
    yt_manager: YandexTrackerManager, issue: dict, incident: Incident
) -> bool:
    pole_is_valid = True

    issue_key = issue['key']
    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id)
    status_key: str = issue['status']['key']

    if not pole_number:
        return pole_is_valid

    try:
        Pole.objects.get(pole=pole_number)
    except Pole.DoesNotExist:
        pole_is_valid = False
        # Номер БС всегда в этом случае делаем None, чтобы не вызывать новую
        # ошибку в будущем:
        yt_manager.update_pole_and_base_station_fields(
            key=issue_key,
            pole_number=None,
            base_station_number=None,
            avr_name=None,
            operator_name=None,
        )
        if status_key != yt_manager.error_status_key:
            comment = f'Неверно указан шифр опоры ({pole_number}).'
            was_status_update = yt_manager.update_issue_status(
                issue_key,
                yt_manager.error_status_key,
                comment
            )
            if was_status_update:
                IncidentManager.add_error_status(incident, comment)

    return pole_is_valid


def check_yt_base_station_incident(
    yt_manager: YandexTrackerManager, issue: dict, incident: Incident
) -> bool:
    base_station_is_valid = True

    issue_key = issue['key']
    base_station_number: Optional[str] = issue.get(
        yt_manager.base_station_global_field_id)
    pole_number: Optional[str] = issue.get(
        yt_manager.pole_number_global_field_id)
    status_key: str = issue['status']['key']

    if not base_station_number:
        return base_station_is_valid

    try:
        base_stations = BaseStation.objects.filter(
            bs_name=base_station_number
        )[:2]
        if len(base_stations) > 1 and pole_number:
            if (
                base_stations[0].pole
                and base_stations[0].pole.pole != pole_number
            ):
                raise Pole.DoesNotExist
        elif len(base_stations) > 1 and not pole_number:
            raise ValueError  # Надо уточнить шифр опоры
        elif not base_stations:
            raise BaseStation.DoesNotExist
        else:
            base_station = base_stations[0]
            if pole_number and base_station.pole.pole != pole_number:
                raise BaseStation.DoesNotExist

    except BaseStation.DoesNotExist:
        base_station_is_valid = False
        yt_manager.update_pole_and_base_station_fields(
            key=issue_key,
            pole_number=pole_number,
            base_station_number=None,
            avr_name=None,
            operator_name=None,
        )
        if status_key != yt_manager.error_status_key:
            comment = (
                'Неверно указан номер базовой станции '
                f'({base_station_number}).'
            )
            was_status_update = yt_manager.update_issue_status(
                issue_key,
                yt_manager.error_status_key,
                comment
            )
            if was_status_update:
                IncidentManager.add_error_status(incident, comment)
    except Pole.DoesNotExist:
        base_station_is_valid = False
        yt_manager.update_pole_and_base_station_fields(
            key=issue_key,
            pole_number=None,
            base_station_number=base_station_number,
            avr_name=None,
            operator_name=None,
        )
        if status_key != yt_manager.error_status_key:
            comment = (
                f'Неверно указан шифр опоры ({pole_number}) для выбранной '
                'базовой станции.'
            )
            was_status_update = yt_manager.update_issue_status(
                issue_key,
                yt_manager.error_status_key,
                comment
            )
            if was_status_update:
                IncidentManager.add_error_status(incident, comment)
    except ValueError:
        base_station_is_valid = False
        yt_manager.update_pole_and_base_station_fields(
            key=issue_key,
            pole_number=None,
            base_station_number=None,
            avr_name=None,
            operator_name=None,
        )
        if status_key != yt_manager.error_status_key:
            comment = (
                f'Неверно указан шифр опоры ({pole_number}) или номер базовой '
                f'станции ({base_station_number}).'
            )
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
    ):
        operator_bs_is_valid = False

    return operator_bs_is_valid


@transaction.atomic
def check_yt_incident_data(
    yt_manager: YandexTrackerManager, issue: dict, logging: Logger,
) -> Optional[bool]:
    """
    Проверка данных в YandexTracker.

    Returns:
        bool | None: Если данные по инциденту корректны вернем True, если нет
        False. Если заявка без YT_DATABASE_GLOBAL_FIELD_ID, тогда None.

    Особенности:
        - Шифр опоры и номер базовой станции в БД и YandexTracker должны
        совпадать.
            - Если эти данные отсутствуют в БД, а в YandexTracker есть,
            тогда проверяем их и если всё в порядке, вносим в БД.
            - Если они отсутсвут в YandexTracker, а в БД есть, тогда удаляем
            эту запись из БД (опора была найдена не верно и диспетчер её
            убрал).
        - Имя оператора и подрядчика по АВР всегда берем из БД.
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
                IncidentManager.add_error_status(incident, comment)
                logging.debug(comment)
        return False

    # Надо проверить, что опора и базовая станция указанные в YandexTracker
    # существуют в базе данных:
    is_valid_pole_number = check_yt_pole_incident(yt_manager, issue, incident)
    incident_pole = incident.pole
    if not is_valid_pole_number:
        logging.debug(f'Ошибка {issue_key}: неверный шифр опоры.')
        return False

    # Синхронизируем данные по опоре:
    if not incident_pole and pole_number:
        incident.pole = Pole.objects.get(pole=pole_number)
        incident.save()
    elif incident_pole and not pole_number:
        incident.pole = None
        incident.save()

    # Синхронизируем данные по базовой станции:
    is_valid_base_station = check_yt_base_station_incident(
        yt_manager, issue, incident)
    incident_bs = incident.base_station
    if not is_valid_base_station:
        logging.debug(f'Ошибка {issue_key}: неверный номер базовой станции.')
        return False

    if not incident_bs and base_station_number:
        incident.base_station = BaseStation.objects.get(
            bs_name=base_station_number)
        incident.save()
    elif incident_bs and not base_station_number:
        incident.base_station = None
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

    if not is_valid_avr_name or not is_valid_operator_bs:
        yt_manager.update_pole_and_base_station_fields(
            key=issue_key,
            pole_number=incident.pole.pole if incident.pole else None,
            base_station_number=(
                incident.base_station.bs_name
            ) if incident.base_station else None,
            avr_name=avr.contractor_name if avr else None,
            operator_name=(
                ', '.join(op.operator_name for op in operator_bs)
            ) if operator_bs else None,
        )
        logging.debug(
            f'Ошибка {issue_key}: неверно указан подрядчик по АВР '
            'или оператор базовой станции.'
        )
        return False

    return True
