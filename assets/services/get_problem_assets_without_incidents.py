from assets.models import Equipment
from incidents.models import Incident
from monitoring.constants import UNDEFINED_POLE_CASE
from monitoring.models import DeviceStatus, MSysModem
from ts.models import Pole


def get_problem_assets_without_incidents() -> dict[Pole, list[MSysModem]]:
    """
    Находит опоры с активным оборудованием, у которых есть проблемы
    и исключает те, по которым уже открыт инцидент.

    Returns:
        Dict[Pole, List[MSysModem]]: Словарь {опора: список проблемных модемов}
    """

    active_equipment_qs = Equipment.objects.filter(is_active=True)

    if not active_equipment_qs.exists():
        return {}

    active_ips = list(
        active_equipment_qs.values_list('modem_ip', flat=True)
    )
    matching_monitoring_qs = MSysModem.objects.filter(
        modem_ip__in=active_ips,
        modem_mac__isnull=False,
        pole_1__isnull=False,
    ).exclude(pole_1=UNDEFINED_POLE_CASE).select_related('pole_1')

    monitoring_lookup: dict[tuple[str], MSysModem] = {}
    for mon in matching_monitoring_qs:
        key = (mon.modem_ip.strip(), mon.modem_mac.upper().strip())
        monitoring_lookup[key] = mon

    active_err_assets: dict[Pole, list[MSysModem]] = {}

    for eq in active_equipment_qs:
        target_key = (eq.modem_ip.strip(), eq.modem_mac.upper().strip())

        if target_key not in monitoring_lookup:
            continue

        mon_obj = monitoring_lookup[target_key]

        devices = (
            MSysModem.objects
            .filter(pole_1=mon_obj.pole_1)
            .exclude(status=DeviceStatus.MODEM_NORMAL)
        ).select_related('pole_1', 'status')

        if not devices.exists():
            continue

        try:
            pole = Pole.objects.get(pole=mon_obj.pole_1.pole.strip())
        except Pole.DoesNotExist:
            continue

        if pole not in active_err_assets:
            active_err_assets[pole] = []

        # Добавляем устройства к списку для опоры:
        active_err_assets[pole].extend(list(devices))

    err_poles = list(active_err_assets)

    err_poles_ids_with_incidents = set(
        Incident.objects
        .filter(pole__in=err_poles, is_incident_finish=False)
        .values_list('pole_id', flat=True)
    )

    final_active_err_assets = {
        pole: devices
        for pole, devices in active_err_assets.items()
        if pole.id not in err_poles_ids_with_incidents
    }

    return final_active_err_assets
