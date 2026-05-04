from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from incidents.services.get_incident_responsible_users import (
    get_responsible_users,
)
from ts.services.get_operators_group import get_operators_group
from users.utils import role_required


@login_required
@role_required()
def incidents_stats(request: HttpRequest) -> HttpResponse:
    responsible_users = get_responsible_users()
    operators_group = get_operators_group()

    context = {
        'today': timezone.localdate(),
        'hours': range(24),
        'responsible_users': responsible_users,
        'operators_group': operators_group,
    }

    return render(request, 'stats/incidents_stats.html', context)
