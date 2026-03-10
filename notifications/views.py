from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django_ratelimit.decorators import ratelimit


@login_required
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notification_list(request: HttpRequest) -> HttpResponse:
    ...


@login_required
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notification_detail(
    request: HttpRequest, notification_id: int
) -> HttpResponse:
    ...
