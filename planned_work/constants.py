from datetime import timedelta

from django.db import models

MAX_PLR_REASON_LEN = 32

MAX_PLR_PER_PAGE = 25
PAGE_SIZE_PLR_CHOICES = [15, MAX_PLR_PER_PAGE, 50, 100, 200, 500]

MAX_PLR_CHANGE_LOG_PER_PAGE = 25

MAX_PLR_EMAILS_LINKS = 25

PLR_CHANGE_LOG_PER_PAGE = 100

CLEANUP_OLD_PLR_CHANGE_LOG_TTL = timedelta(days=365)

PLR_CHANGE_LOG_BATCH_SIZE = 1000


class PlannedWorkReason(models.TextChoices):
    """Причины проведения плановых работ"""
    POWER_OFF = ('power_off', 'Отключение питания')
    PREVENTIVE_MAINTENANCE = (
        'preventive_maintenance', 'Плановое обслуживание'
    )
    EQUIPMENT_UPGRADE = ('equipment_upgrade', 'Модернизация оборудования')
    CABLE_REPLACEMENT = ('cable_replacement', 'Замена кабельной линии')
    INSTALLATION = ('installation', 'Установка нового оборудования')
    INSPECTION = ('inspection', 'Инспекция / Обследование')
    OTHER = ('other', 'Иное')


PLANNED_WORK_REASON_DESCRIPTIONS = {
    PlannedWorkReason.POWER_OFF: (
        'Плановое отключение электропитания для проведения работ. '
        'Объект может быть недоступен в указанное время.'
    ),
    PlannedWorkReason.PREVENTIVE_MAINTENANCE: (
        'Регулярное профилактическое обслуживание: диагностика, чистка, '
        'проверка узлов и замена расходных материалов по графику.'
    ),
    PlannedWorkReason.EQUIPMENT_UPGRADE: (
        'Обновление или модернизация существующего оборудования для '
        'повышения надёжности и качества работы.'
    ),
    PlannedWorkReason.CABLE_REPLACEMENT: (
        'Замена или восстановление кабельной линии: прокладка новых кабелей, '
        'устранение повреждений.'
    ),
    PlannedWorkReason.INSTALLATION: (
        'Монтаж и ввод в эксплуатацию нового оборудования: антенны, '
        'базовые станции, коммутаторы, источники питания и т.д.'
    ),
    PlannedWorkReason.INSPECTION: (
        'Обследование объекта: проверка состояния оборудования, помещений, '
        'креплений и заземления.'
    ),
    PlannedWorkReason.OTHER: (
        'Другая причина, не входящая в стандартные категории.'
    ),
}


class PlannedWorkStatus(models.TextChoices):
    """Статусы плановой работы"""
    PLANNED = 'planned', 'В планах'
    IN_PROGRESS = 'in-progress', 'В работе'
    COMPLETED = 'closed', 'Завершена'
