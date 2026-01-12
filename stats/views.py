from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from users.utils import role_required


@login_required
@role_required()
def incidents_stats(request):
    return render(request, 'stats/incidents_stats.html')
