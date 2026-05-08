from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from users.utils import role_required

from .constants import (
    GENERAL_DISPATCH_STATISTICS_SLUG,
    GENERAL_DISPATCH_STATISTICS_UID,
    GRAFANA_PUBLIC_URL,
)


@login_required
@role_required()
def grafana_general_dashboard(request: HttpRequest) -> HttpResponse:
    theme = request.COOKIES.get('site_theme', 'auto')

    query_params = {
        'timezone': 'Europe%2FMoscow',
        'theme': theme,
    }

    base_url = (
        f'{GRAFANA_PUBLIC_URL}/'
        f'{GENERAL_DISPATCH_STATISTICS_SLUG}/'
        f'{GENERAL_DISPATCH_STATISTICS_UID}'
    )

    params = urlencode(query_params)
    full_url = f'{base_url}?{params}&kiosk'

    context = {'grafana_url': full_url}

    return render(request, 'metrics/general_metrics.html', context)
