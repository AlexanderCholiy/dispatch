from urllib.parse import urlencode

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from users.utils import role_required

from .constants import (
    GENERAL_DISPATCH_STATISTICS_SLUG,
    GENERAL_DISPATCH_STATISTICS_UID,
    GRAFANA_PUBLIC_URL,
)


@login_required
@role_required()
def grafana_general_dashboard(request: HttpRequest) -> HttpResponse:
    user_theme = request.COOKIES.get('site_theme', 'auto')

    now = timezone.now()

    first_day_current = now.replace(day=1)
    first_day_prev_month = first_day_current - relativedelta(months=1)

    utc_date = first_day_prev_month.astimezone(timezone.utc)

    from_date_str = utc_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    query_params = {
        'from': from_date_str,
        'to': 'now',
        'timezone': 'Europe%2FMoscow',
        'var-dispatch': '$__all',
        'theme': user_theme,
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
