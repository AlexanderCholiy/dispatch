from typing import Optional

from django.core.cache import cache
from django.db.models import Prefetch

from assets.constants import (
    CACHE_ASSETS_STATUS_TTL,
    CACHE_KEY_ASSETS_STATUS_PREFIX,
)
from assets.models import Equipment
from core.loggers import assets_logger
from incidents.models import Comment, Incident
from monitoring_2.constants import MODEM_NORMAL_STATUS_ID, UNDEFINED_POLE_CASE

# Импортируем из мониторинга только то, что относится к оборудованию
from monitoring_2.models import Modem, ModemPoleRealtion

# Возвращаем импорт оригинальной модели Pole
from ts.models import Pole
from users.models import User


def get_problem_assets_without_incidents(
    bot_user: Optional[User]
) -> dict[Pole, list[Modem]]:
    """
    Находит опоры (ts.models.Pole) с активным оборудованием, у которых есть
    проблемы, и исключает те, по которым уже открыт инцидент.

    Также обновляет кэш статусов для каждого устройства и эскалирует
    инциденты с автозакрытием.

    Returns:
        dict[Pole, list[Modem]]: Словарь {ts_опора: список проблемных модемов}
    """

    active_equipment_qs = Equipment.objects.filter(is_active=True)

    if not active_equipment_qs.exists():
        return {}

    # Собираем активные IP-адреса для фильтрации
    active_ips = list(
        active_equipment_qs.values_list('modem_ip', flat=True)
    )

    # Запрашиваем модемы из monitoring_2, подтягивая их ГИС-опоры
    matching_monitoring_qs = (
        Modem.objects.filter(
            ip__in=active_ips,
            mac__isnull=False,
            modem_pole_relations__isnull=False,
            modem_pole_relations__dismantled=False,
        )
        .exclude(
            modem_pole_relations__pole__pole=UNDEFINED_POLE_CASE,
        )
        .select_related('level', 'status')
        .prefetch_related(
            Prefetch(
                'modem_pole_relations',
                queryset=(
                    ModemPoleRealtion.objects
                    .filter(dismantled=False)
                    .select_related('pole')
                    .order_by('-id')
                )
            )
        )
        .distinct()
    )

    # Строим lookup-словарь по ключу (IP, MAC)
    monitoring_lookup: dict[tuple[str, str], Modem] = {}
    for mon in matching_monitoring_qs:
        key = (mon.ip.strip(), mon.mac.upper().strip())
        monitoring_lookup[key] = mon

    # Временный словарь, где ключом будет строковый шифр опоры (pole_code)
    active_err_by_code: dict[str, list[Modem]] = {}
    # Словарь для кэширования соответствия шифра и ГИС-объекта
    # (для логов и сообщений)
    pole_names_lookup: dict[str, str] = {}

    for eq in active_equipment_qs:
        target_key = (eq.modem_ip.strip(), eq.modem_mac.upper().strip())
        cache_key = (
            f'{CACHE_KEY_ASSETS_STATUS_PREFIX}{target_key[0]}:{target_key[1]}'
        )

        if target_key not in monitoring_lookup:
            cache.set(
                cache_key,
                '⚠️ Нет в мониторинге',
                timeout=CACHE_ASSETS_STATUS_TTL
            )
            continue

        mon_obj = monitoring_lookup[target_key]

        cached_relations: list[ModemPoleRealtion] = list(
            mon_obj.modem_pole_relations.all()
        )
        active_relation = cached_relations[0] if cached_relations else None

        if not active_relation or not active_relation.pole:
            cache.set(
                cache_key,
                '❌ Привязка к опоре отсутствует',
                timeout=CACHE_ASSETS_STATUS_TTL
            )
            continue

        monitoring_pole_obj = active_relation.pole
        mon_pole_code = monitoring_pole_obj.pole.strip()

        if mon_pole_code == UNDEFINED_POLE_CASE:
            cache.set(
                cache_key,
                '❌ Привязка к опоре отсутствует',
                timeout=CACHE_ASSETS_STATUS_TTL
            )
            continue

        pole_names_lookup[mon_pole_code] = mon_pole_code

        # Проверяем проблемы на данной ГИС-опоре
        devices_with_errors = list(
            Modem.objects.filter(
                modem_pole_relations__pole=monitoring_pole_obj,
                modem_pole_relations__dismantled=False
            )
            .exclude(status_id=MODEM_NORMAL_STATUS_ID)
            .select_related('level', 'status')
            .distinct()
        )
        has_problems_on_pole = len(devices_with_errors) > 0

        is_device_problematic = mon_obj.status_id != MODEM_NORMAL_STATUS_ID

        level_label = (
            mon_obj.level.description
            if mon_obj.level else f'щит №{mon_obj.level_id}'
        )
        status_label = (
            mon_obj.status.level_description
            if mon_obj.status else f'№{mon_obj.status_id}'
        )

        if is_device_problematic:
            msg = f'🔴 {level_label} [{status_label}] на опоре {mon_pole_code}'
        else:
            msg = (
                (
                    f'🟠 {level_label} [{status_label}], '
                    f'но есть проблемы у других устройств '
                    f'(опора {mon_pole_code})'
                )
                if has_problems_on_pole
                else (
                    f'✅ {level_label} [{status_label}] '
                    f'(опора {mon_pole_code})'
                )
            )

        cache.set(cache_key, msg, timeout=CACHE_ASSETS_STATUS_TTL)

        if not has_problems_on_pole:
            continue

        if mon_pole_code not in active_err_by_code:
            active_err_by_code[mon_pole_code] = []

        active_err_by_code[mon_pole_code].extend(devices_with_errors)

    if not active_err_by_code:
        return {}

    # Вытягиваем из базы реальные объекты ts.models.Pole по собранным шифрам
    ts_poles = Pole.objects.filter(pole__in=list(active_err_by_code.keys()))

    # Пересобираем словарь, где ключом теперь является объект ts.models.Pole
    active_err_assets: dict[Pole, list[Modem]] = {}
    for ts_pole in ts_poles:
        code = ts_pole.pole.strip()
        devices = active_err_by_code.get(code, [])

        # Убираем возможные дубликаты модемов для этой опоры
        seen_modems = set()
        unique_devices = []
        for d in devices:
            if d.id not in seen_modems:
                seen_modems.add(d.id)
                unique_devices.append(d)

        active_err_assets[ts_pole] = unique_devices

    err_poles = list(active_err_assets.keys())
    if not err_poles:
        return {}

    # Находим ID опор ts.models.Pole, по которым уже открыты инциденты
    err_poles_ids_with_incidents = set(
        Incident.objects
        .filter(pole__in=err_poles, is_incident_finish=False)
        .values_list('pole_id', flat=True)
    )

    comments_to_add = []
    incidents_to_bulk_update = []

    # Выбираем инциденты, завязанные на ts.models.Pole, требующие отмены
    # автозакрытия
    incidents_to_update = (
        Incident.objects.filter(
            pole__in=err_poles,
            is_incident_finish=False,
            auto_close_date__isnull=False,
        )
        .select_related('pole')
    )

    for incident in incidents_to_update:
        err_devices = active_err_assets.get(incident.pole, [])
        if not err_devices:
            continue

        incident.auto_close_date = None
        incident.was_read = False
        incidents_to_bulk_update.append(incident)

        status_groups: list[str] = []

        for eq in err_devices:
            if eq.status_id == MODEM_NORMAL_STATUS_ID:
                continue

            eq_level_label = (
                eq.level.description if eq.level else f'Тип {eq.level_id}'
            )
            eq_status_label = (
                eq.status.level_description
                if eq.status else f'Статус {eq.status_id}'
            )

            status_groups.append(
                f'- {eq_level_label}: {eq.ip.strip()} [{eq_status_label}]'
            )

        comment_text = (
            'Автозакрытие отменено. Проблема с оборудованием сохраняется:\n'
            f'{"\n".join(status_groups)}'
        ).strip()

        if bot_user:
            comments_to_add.append({
                'incident': incident,
                'content': comment_text,
            })

    # Массовое обновление инцидентов
    if incidents_to_bulk_update:
        Incident.objects.bulk_update(
            incidents_to_bulk_update,
            ['auto_close_date', 'was_read']
        )
        assets_logger.debug(
            f'Пакетно обновлено {len(incidents_to_bulk_update)} инцидентов.'
        )

    # Массовое создание комментариев
    if comments_to_add and bot_user:
        comment_objects = [
            Comment(
                incident=item['incident'],
                content=item['content'],
                author=bot_user,
            )
            for item in comments_to_add
        ]
        Comment.objects.bulk_create(comment_objects)

    # Итоговый результат: отдаем только те опоры ts.models.Pole,
    # по которым инциденты ещё не созданы
    final_active_err_assets: dict[Pole, list[Modem]] = {}
    for pole_item, devices in active_err_assets.items():
        if pole_item.id not in err_poles_ids_with_incidents:
            final_active_err_assets[pole_item] = devices

    return final_active_err_assets
