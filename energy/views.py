from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit

from users.models import Roles
from users.utils import role_required

from .constants import (
    MAX_ENERGY_INFO_CACHE_SEC,
    PAGE_SIZE_REQUESTS_CHOICES,
    REQUESTS_PER_PAGE,
)
from .models import (
    Appeal,
    AppealAttr,
    AppealStatus,
    Claim,
    ClaimAttr,
    ClaimStatus,
    Company,
    Declarant,
)


@login_required
@role_required([Roles.ENERGY])
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def energy_companies(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()

    sort = (
        request.GET.get('sort_energy_companies')
        or request.COOKIES.get('sort_energy_companies')
        or 'desc'
    )

    per_page = int(
        request.GET.get('per_page')
        or request.COOKIES.get('per_page_root')
        or REQUESTS_PER_PAGE
    )

    request_type = (
        request.GET.get('type')
        or request.COOKIES.get('type')
        or 'claims'
    )
    is_claims = request_type == 'claims'

    if per_page not in PAGE_SIZE_REQUESTS_CHOICES:
        params = request.GET.copy()
        params['per_page'] = REQUESTS_PER_PAGE
        return redirect(f'{request.path}?{params.urlencode()}')

    company_id = (
        request.GET.get('company')
        or request.COOKIES.get('company')
    )

    declarant_id = (
        request.GET.get('declarant')
        or request.COOKIES.get('declarant')
    )

    if is_claims:
        latest_status_subquery = ClaimStatus.objects.filter(
            claim_id=OuterRef('id')
        ).order_by('-date', '-created_at', '-id')
    else:
        latest_status_subquery = AppealStatus.objects.filter(
            appeal_id=OuterRef('id')
        ).order_by('-date', '-created_at', '-id')

    base_qs = (
        Claim if is_claims else Appeal
    ).objects.select_related('declarant', 'company').annotate(
        latest_status_name=Subquery(latest_status_subquery.values('name')[:1]),
        latest_status_date=Subquery(latest_status_subquery.values('date')[:1]),
    )

    if company_id:
        base_qs = base_qs.filter(company__id=company_id)

    if declarant_id:
        base_qs = base_qs.filter(declarant__id=declarant_id)

    if query:
        base_qs = base_qs.filter(number__icontains=query).distinct()

    base_qs = (
        base_qs.order_by('id')
    ) if sort == 'asc' else base_qs.order_by('-id')

    paginator = Paginator(base_qs.values_list('id', flat=True), per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_ids = list(page_obj.object_list)

    AttrModel = ClaimAttr if is_claims else AppealAttr
    relation_field = 'claim' if is_claims else 'appeal'

    company_requests_qs = (
        Claim if is_claims else Appeal
    ).objects.filter(id__in=page_ids).select_related(
        'declarant', 'company'
    ).annotate(
        latest_status_name=Subquery(latest_status_subquery.values('name')[:1]),
        latest_status_date=Subquery(latest_status_subquery.values('date')[:1]),
        grid=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1010
            ).values('text')[:1]
        ),
        filial=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1020
            ).values('text')[:1]
        ),
        claim_date=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1030
            ).values('text')[:1]
        ),
        company_link=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1040
            ).values('text')[:1]
        ),
        appeal_date=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=2030
            ).values('text')[:1]
        ),
        appeal_subject=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=2050
            ).values('text')[:1]
        ),
        appeal_text=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=2060
            ).values('text')[:1]
        ),
        pole=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1000
            ).values('text')[:1]
        ),
        claim_for_appeal=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=2070
            ).values('text')[:1]
        ),
        inner_claim_number=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1080
            ).values('text')[:1]
        ),
        claim_comment=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1090
            ).values('text')[:1]
        ),
        object_adress=Subquery(
            AttrModel.objects.filter(
                **{relation_field: OuterRef('id')},
                attr_type__attribute_id=1100
            ).values('text')[:1]
        ),
    )

    company_requests = sorted(
        company_requests_qs, key=lambda i: page_ids.index(i.id)
    )

    companies = cache.get_or_set(
        'energy_filter_companies',
        lambda: list(
            Company.objects.only('id', 'name').order_by('name')
        ),
        MAX_ENERGY_INFO_CACHE_SEC,
    )

    declarants = cache.get_or_set(
        'energy_filter_declarants',
        lambda: list(
            Declarant.objects.only('id', 'name').order_by('name')
        ),
        MAX_ENERGY_INFO_CACHE_SEC,
    )

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    context = {
        'page_obj': page_obj,
        'company_requests': company_requests,
        'search_query': query,
        'page_url_base': page_url_base,
        'companies': companies,
        'declarants': declarants,
        'selected': {
            'per_page': per_page,
            'sort': sort,
            'type': request_type,
        },
        'page_size_choices': PAGE_SIZE_REQUESTS_CHOICES,
    }

    return render(request, 'energy/energy_companies.html', context)
