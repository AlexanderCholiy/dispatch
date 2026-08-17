from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django_ratelimit.decorators import ratelimit

from core.services.formatters import truncate_text
from emails.models import EmailMessage
from incidents.models import Incident
from max.constants import ALLOWED_INCIDENT_TYPES, MaxNotificationStatus
from max.forms import MaxConfirmNotificationForm
from max.services.format_incident_message import format_incident_message
from max.services.get_wait_message import (
    get_wait_message,
    save_notification_status,
)
from max.tasks import send_max_incident_notification
from users.models import Roles, User
from users.utils import role_required

from .constants import MAX_COMMENT_LEN


@login_required
@role_required(allowed_roles=[Roles.DISPATCH])
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def notify_max_incident(
    request: HttpRequest, incident_id: int
) -> HttpResponseRedirect:
    incident = get_object_or_404(
        Incident.objects.select_related(
            'pole',
            'base_station',
            'incident_type',
            'incident_subtype',
            'pole__avr_contractor'
        ).prefetch_related('base_station__operator',),
        id=incident_id
    )

    template_name = 'max/confirm_incident_notification.html'

    errors = []

    if incident.is_incident_finish:
        errors.append('Нельзя отправить уведомление по закрытому инциденту.')

    if not incident.pole:
        errors.append(
            'Прежде чем отправлять уведомление, необходимо указать шифр опоры.'
        )

    if not incident.incident_type:
        errors.append(
            'Прежде чем отправлять уведомление, необходимо указать '
            'тип проблемы.'
        )

    if (
        incident.incident_type
        and incident.incident_type.name not in ALLOWED_INCIDENT_TYPES
    ):
        type_name = incident.incident_type.name

        allowed_names = ', '.join([t for t in ALLOWED_INCIDENT_TYPES])

        errors.append(
            f'Тип "{type_name}" не поддерживается для отправки в MAX. '
            f'Доступные типы: {allowed_names}.'
        )

    if errors:
        for error_msg in errors:
            messages.error(request, error_msg)

        return redirect('incidents:incident_detail', incident_id=incident.id)

    user: User = request.user

    wait_msg = get_wait_message(incident_id)
    if wait_msg:
        messages.warning(request, wait_msg)
        return redirect('incidents:incident_detail', incident_id=incident.id)

    markdown_text, plain_text = format_incident_message(incident)

    if request.method == 'GET':
        preview_comment = EmailMessage.objects.filter(
            email_incident=incident,
        ).order_by('email_date', 'id').first()

        initial_data = {}
        if preview_comment and preview_comment.email_body:
            initial_data['text'] = truncate_text(
                preview_comment.email_body, MAX_COMMENT_LEN
            )

        form = MaxConfirmNotificationForm(initial=initial_data)

        return render(request, template_name, {
            'incident': incident,
            'preview_text': plain_text,
            'form': form,
        })
    elif request.method == 'POST':
        form = MaxConfirmNotificationForm(request.POST)
        if form.is_valid():
            user_comment = form.cleaned_data['text']
            save_notification_status(
                incident_id, MaxNotificationStatus.PENDING
            )

            messages.info(
                request, 'Уведомление формируется и отправляется в MAX.'
            )

            send_max_incident_notification.delay(
                incident_id=incident.id,
                sender_user_id=user.id,
                text=markdown_text,
                comment=user_comment,
            )

        else:
            return render(
                request, template_name, {
                    'incident': incident,
                    'preview_text': plain_text,
                    'form': form,
                }
            )

    return redirect(
        'incidents:incident_detail', incident_id=incident.id
    )
