from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django_ratelimit.decorators import ratelimit

from users.utils import role_required

from .constants import INCIDENTS_PER_PAGE


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def index(request: HttpRequest) -> HttpResponse:
    template_name = 'incidents/index.html'

    query = request.GET.get('q', '').strip()
    paginator = Paginator([], INCIDENTS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    context = {
        'page_obj': page_obj,
        'search_query': query,
        'page_url_base': page_url_base,
    }
    return render(request, template_name, context)
