from core.constants import CURRENT_TZ
from emails.constants import DISPATCHER_SIGNATURE
from incidents.models import Incident


def get_incident_signature(
    incident: Incident, email_2_contractor: bool = False
) -> str:
    signature: list[str] = ['\n'] if not email_2_contractor else []
    pole = incident.pole

    if not email_2_contractor:
        registration_date = (
            incident.incident_date.astimezone(CURRENT_TZ)
            .strftime('%Y-%m-%d %H:%M')
        )
        signature.append(f'• Дата регистрации: {registration_date} (МСК)')

    if pole and not email_2_contractor:
        signature.append(f'• Шифр опоры: {pole.pole}')

        if pole.address:
            signature.append(f'• Адрес: {pole.address}')

        region = pole.region.region_ru or pole.region.region_en
        if not pole.address:
            signature.append(f'• Регион: {region}')

    signature.append('\nПожалуйста, не меняйте тему письма.\n\n')

    signature.append(f'{DISPATCHER_SIGNATURE}')

    return '\n'.join(signature)
