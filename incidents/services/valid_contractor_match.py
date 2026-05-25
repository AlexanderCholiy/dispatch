from incidents.models import Incident
from users.models import User


def is_valid_contractor_match(user: User, incident: Incident) -> bool:
    """
    Проверяет, что инцидент принадлежит тому же подрядчику, который делает
    запрос.
    """
    pole = incident.pole

    if not pole or not pole.avr_contractor:
        return False

    return pole.avr_contractor == user.avr_contractor
