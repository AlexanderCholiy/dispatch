from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView
from django_ratelimit.decorators import ratelimit

from incidents.models import Incident

from .constants import (
    NOTIFICATIONS_PER_PAGE,
    PAGE_SIZE_NOTIFICATIONS_CHOICES,
)
from .forms import NotificationForm
from .models import Notification, NotificationLevel


@login_required
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notification_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()

    levels = [n for n in NotificationLevel]

    read = (
        request.GET.get('read', '').strip()
        or request.COOKIES.get('read', '').strip()
    )

    if read == 'true':
        read = True
    elif read == 'false':
        read = False
    else:
        read = None

    level = (
        request.GET.get('level', '').strip().lower()
        or request.COOKIES.get('level', '').strip().lower()
    )
    level = level if (
        level and level in [r.value for r in levels]
    ) else ''

    per_page = int(
        request.GET.get('per_page')
        or request.COOKIES.get('per_page_notifications')
        or NOTIFICATIONS_PER_PAGE
    )

    sort = (
        request.GET.get('sort_notifications')
        or request.COOKIES.get('sort_notifications')
        or 'asc'
    )

    if per_page not in PAGE_SIZE_NOTIFICATIONS_CHOICES:
        params = request.GET.copy()
        params['per_page'] = NOTIFICATIONS_PER_PAGE
        return redirect(f"{request.path}?{params.urlencode()}")

    base_qs = (
        Notification.objects
        .select_related('user')
        .filter(user=request.user)
    )

    if query:
        base_qs = base_qs.filter(title__icontains=query)

    if read is not None:
        base_qs = base_qs.filter(read=read)

    if level:
        base_qs = base_qs.filter(level=level)

    if sort == 'asc':
        base_qs = base_qs.order_by('send_at', 'created_at', 'id')
    else:
        base_qs = base_qs.order_by('-send_at', '-created_at', '-id')

    paginator = Paginator(base_qs.values_list('id', flat=True), per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_ids = list(page_obj.object_list)

    notifications_qs = (
        Notification.objects.filter(id__in=page_ids)
        .select_related('user')
    )
    id_index = {id_: i for i, id_ in enumerate(page_ids)}
    notifications = sorted(notifications_qs, key=lambda n: id_index[n.id])

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    context = {
        'page_obj': page_obj,
        'notifications': notifications,
        'search_query': query,
        'page_url_base': page_url_base,
        'levels': levels,
        'selected': {
            'per_page': per_page,
            'sort': sort,
            'read': read,
            'level': level,
        },
        'page_size_choices': PAGE_SIZE_NOTIFICATIONS_CHOICES,
    }

    return render(request, 'notifications/notifications_list.html', context)


@login_required
@ratelimit(key='user_or_ip', rate='20/m', block=True)
def notification_detail(
    request: HttpRequest, notification_id: int
) -> HttpResponse:
    notification = get_object_or_404(
        Notification, pk=notification_id, user=request.user
    )

    if request.method == 'POST':
        form = NotificationForm(request.POST, instance=notification)
        if form.is_valid():
            notification: Notification = form.save()
            title = notification.title
            messages.success(request, f'Уведомление "{title}" обновлено')
            return redirect('notifications:notification_list')
    else:
        form = NotificationForm(instance=notification)

    context = {
        'form': form,
        'notification': notification
    }
    return render(request, 'notifications/notification_form.html', context)


class NotificationCreateView(CreateView):
    model = Notification
    form_class = NotificationForm
    template_name = 'notifications/notification_form.html'
    success_url = reverse_lazy('notifications:notification_list')

    def form_valid(self, form):
        form.instance.user = self.request.user

        notification: Notification = form.instance
        title = notification.title

        messages.success(
            self.request, f'Уведомление "{title}" успешно добавлено'
        )

        return super().form_valid(form)


class NotificationCreateFromIncidentView(CreateView):
    model = Notification
    form_class = NotificationForm
    template_name = 'notifications/notification_form.html'

    def get_initial(self):
        initial = super().get_initial()

        incident_id = self.kwargs.get('incident_id')
        incident = get_object_or_404(Incident, pk=incident_id)

        initial['title'] = str(incident)

        return initial

    def form_valid(self, form):
        form.instance.user = self.request.user
        incident_id = self.kwargs.get('incident_id')

        data = form.instance.data or {}
        data['incident_id'] = incident_id
        form.instance.data = data

        notification: Notification = form.instance
        title = notification.title

        messages.success(
            self.request,
            f'Уведомление "{title}" успешно добавлено.'
        )

        return super().form_valid(form)

    def get_success_url(self):
        incident_id = self.kwargs.get('incident_id')
        return reverse(
            'incidents:incident_detail',
            kwargs={'incident_id': incident_id},
        )
