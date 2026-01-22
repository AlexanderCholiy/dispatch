from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from users.utils import role_required


@login_required
@role_required()
def incidents_stats(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    return render(request, 'stats/incidents_stats.html', {'today': today})
