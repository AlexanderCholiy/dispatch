from datetime import datetime, timedelta
from typing import Optional

from axes.helpers import get_client_ip_address
from axes.models import AccessAttempt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeDoneView,
    PasswordResetCompleteView,
    PasswordResetDoneView,
    PasswordResetView
)
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.timezone import now
from django_ratelimit.decorators import ratelimit

from core.constants import DJANGO_LOG_ROTATING_FILE
from core.loggers import LoggerFactory
from core.utils import timedelta_to_human_time
from incidents.models import Incident

from .constants import PAGE_SIZE_USERS_CHOICES, USERS_PER_PAGE
from .forms import (
    ChangeEmailForm,
    UserForm,
    UserRegisterForm,
    WorkScheduleForm,
)
from .models import PendingUser, Roles, User, WorkSchedule
from .tasks import send_password_reset_email_task
from .utils import (
    role_required,
    send_activation_email,
    send_confirm_email,
)

django_logger = LoggerFactory(__name__, DJANGO_LOG_ROTATING_FILE).get_logger()


@method_decorator(
    ratelimit(key='user_or_ip', rate='5/m', block=True),
    name='dispatch',
)
class CustomPasswordResetDoneView(PasswordResetDoneView):
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('password_reset_allowed'):
            messages.warning(
                request,
                'Эта страница доступна только после запроса на восстановление '
                'пароля.'
            )
            return redirect('password_reset')

        del request.session['password_reset_allowed']
        return super().dispatch(request, *args, **kwargs)


@method_decorator(
    ratelimit(key='user_or_ip', rate='5/m', block=True),
    name='dispatch',
)
class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    def get(self, request, *args, **kwargs):
        messages.success(request, 'Ваш новый пароль сохранён.')

        if request.user.is_authenticated:
            return redirect('users:profile')
        return redirect('login')


@method_decorator(
    ratelimit(key='user_or_ip', rate='5/m', block=True, method='POST'),
    name='dispatch',
)
class CustomPasswordResetView(PasswordResetView):

    def form_valid(self, form):
        """Анти-спам + отправка письма через Celery."""
        email = form.cleaned_data['email'].lower()

        key = f'password_reset_throttle:{email}'
        last_time: Optional[datetime] = cache.get(key)

        cooldown: timedelta = settings.AXES_COOLOFF_TIME

        if last_time:
            elapsed = now() - last_time
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                wait_human = timedelta_to_human_time(remaining)
                messages.warning(
                    self.request,
                    f'Запрос уже был отправлен. Подождите {wait_human}.'
                )
                return redirect('password_reset')

        cache.set(key, now(), timeout=int(cooldown.total_seconds()))

        try:
            user = User.objects.get(email=email)

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            reset_path = reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uid, 'token': token},
            )
            reset_password_link = self.request.build_absolute_uri(reset_path)
            domain = self.request.get_host()

            send_password_reset_email_task.delay(
                user_id=user.pk,
                domain=domain,
                reset_password_link=reset_password_link,
            )

        except User.DoesNotExist:
            pass

        self.request.session['password_reset_allowed'] = True

        return redirect('password_reset_done')


@method_decorator(
    ratelimit(key='user_or_ip', rate='10/m', block=True, method='POST'),
    name='dispatch'
)
class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    def get(self, request, *args, **kwargs):
        messages.success(request, 'Пароль успешно изменён!')
        return redirect('users:profile')


@method_decorator(
    ratelimit(key='user_or_ip', rate='10/m', block=True, method='POST'),
    name='dispatch'
)
class CustomLoginView(LoginView):

    def form_invalid(self, form):
        response = super().form_invalid(form)

        username = self.request.POST.get('username', '')
        user = User.objects.filter(
            Q(username=username) | Q(email=username)
        ).first()
        username_real = user.email if user else username

        ip_address = get_client_ip_address(self.request)
        failure_limit = getattr(settings, 'AXES_FAILURE_LIMIT', 3)
        cool_off = getattr(settings, 'AXES_COOLOFF_TIME', timedelta(minutes=5))

        recent_attempt = AccessAttempt.objects.filter(
            username=username_real,
            ip_address=ip_address,
            failures_since_start__gt=0,
        ).order_by('-attempt_time').first()

        if recent_attempt:
            failures = recent_attempt.failures_since_start
            remaining = max(failure_limit - failures, 0)

            if remaining > 0:
                messages.warning(
                    self.request,
                    f'Осталось попыток входа: {remaining}'
                )
            else:
                lock_start_time = recent_attempt.attempt_time
                cooldown_end = lock_start_time + cool_off
                time_remaining = cooldown_end - now()

                seconds_left = int(time_remaining.total_seconds())
                if seconds_left > 0:
                    messages.error(
                        self.request,
                        f'Повторите попытку через {seconds_left} секунд. '
                        'Каждая новая попытка продлевает таймер!'
                    )

        return response


@ratelimit(key='user_or_ip', rate='20/m', block=True, method='POST')
def register(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            pending_user = form.save()
            send_activation_email(pending_user, request)
            messages.success(
                request,
                'На указанную вами почту была отправлена ссылка для '
                'подтверждения.'
            )
            return redirect('login')
    else:
        form = UserRegisterForm()

    context = {'form': form}
    return render(request, 'registration/register.html', context)


def activate(
    request: HttpRequest, uidb64: str, token: str
) -> HttpResponseRedirect:
    pending_user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        pending_user = PendingUser.objects.get(pk=uid)
    except (
        TypeError,
        ValueError,
        OverflowError,
        PendingUser.DoesNotExist,
    ) as e:
        if pending_user:
            django_logger.warning(
                f'Ошибка активации PendingUser по email с uid {uid}'
            )
        else:
            django_logger.exception(
                'Ошибка подтверждения email для PendingUser:', e
            )
    if (
        pending_user
        and default_token_generator.check_token(pending_user, token)
    ):
        pending_user.delete()
        User.objects.create(
            username=pending_user.username,
            email=pending_user.email,
            password=pending_user.password,  # hashed
            is_active=True
        )
        messages.success(request, 'Ваш аккаунт был успешно активирован.')
        return redirect('login')

    messages.error(
        request,
        'Ссылка для активации недействительна или уже была использована. '
        'Пожалуйста, пройдите регистрацию заново.'
    )
    return redirect('users:register')


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='10/m', block=True, method='POST')
def change_email(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ChangeEmailForm(request.POST, instance=request.user)
        if form.is_valid():
            new_email = form.cleaned_data['email']
            user: User = request.user
            pending_user = PendingUser.objects.create(
                username=user.temporary_username,
                email=new_email,
                password=user.password,
            )
            send_confirm_email(pending_user, request)
            messages.success(
                request,
                'На указанную вами почту была отправлена ссылка для '
                'подтверждения.'
            )
            return redirect('users:profile')
        else:
            for name, errors in form.errors.items():
                if name == '__all__':
                    for error in set(errors):
                        messages.error(request, error)
    else:
        form = ChangeEmailForm(instance=request.user)

    context = {'form': form}
    return render(request, 'users/email_change_form.html', context)


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def confirm_email_change(
    request: HttpRequest, uidb64: str, token: str
) -> HttpResponse:
    pending_user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        pending_user = PendingUser.objects.get(pk=uid)
    except (
        TypeError,
        ValueError,
        OverflowError,
        PendingUser.DoesNotExist,
    ) as e:
        if pending_user:
            django_logger.warning(
                f'Ошибка подтверждения email для PendingUser с uid {uid}'
            )
        else:
            django_logger.exception(
                'Ошибка подтверждения email для PendingUser:', e
            )

    if (
        pending_user
        and default_token_generator.check_token(pending_user, token)
    ):
        user = User.objects.get(username=pending_user.original_username)
        pending_user.delete()
        user.email = pending_user.email
        user.save()
        messages.success(
            request,
            'Ваш email был успешно изменен и подтвержден.'
        )
        return redirect('users:change_email')
    messages.error(
        request,
        'Ссылка для подтверждения недействительна или устарела. '
        'Пожалуйста, запросите смену email еще раз.'
    )
    return redirect('users:change_email')


@login_required
@role_required()
@ratelimit(key='user_or_ip', rate='20/m', block=True, method='POST')
def profile(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлён')
            return redirect('users:profile')
    else:
        form = UserForm(instance=request.user)

    context = {'form': form}
    return render(request, 'users/profile_form.html', context)


@login_required
@role_required()
def users_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip().lower()

    per_page = int(
        request.GET.get('per_page')
        or request.COOKIES.get('per_page_emails')
        or USERS_PER_PAGE
    )

    if per_page not in PAGE_SIZE_USERS_CHOICES:
        params = request.GET.copy()
        params['per_page'] = USERS_PER_PAGE
        return redirect(f"{request.path}?{params.urlencode()}")

    roles = [role for role in Roles if role != Roles.GUEST]
    role_filter = role_filter if (
        role_filter and role_filter in [r.value for r in roles]
    ) else ''

    users = (
        User.objects
        .select_related(
            'work_schedule',
        )
        .exclude(role=Roles.GUEST).exclude(is_active=False)
        .order_by('username')
    )

    if role_filter:
        users = users.filter(role=role_filter)

    if query:
        words = {w.strip().lower() for w in query.split(' ') if w.strip()}
        q_filter = Q()
        for word in words:
            q_filter |= Q(username__icontains=word)
            q_filter |= Q(first_name__icontains=word)
            q_filter |= Q(last_name__icontains=word)

        new_user_keywords = ['новый', 'пользователь']
        if any(word in words for word in new_user_keywords):
            q_filter |= Q(first_name__exact='') & Q(last_name__exact='')

        users = users.filter(q_filter)

    paginator = Paginator(users, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_url_base = f'?{query_params.urlencode()}&' if query_params else '?'

    context = {
        'page_obj': page_obj,
        'search_query': query,
        'page_url_base': page_url_base,
        'roles': roles,
        'selected': {
            'role': role_filter,
            'per_page': per_page,
        },
        'page_size_choices': PAGE_SIZE_USERS_CHOICES,
    }

    return render(request, 'users/users.html', context)


@login_required
@role_required()
def user_detail(request: HttpRequest, user_id: int):
    user = get_object_or_404(
        User.objects.select_related('work_schedule'),
        pk=user_id,
        is_active=True
    )

    incidents = Incident.objects.filter(responsible_user=user)

    last_week = now() - timedelta(days=7)

    stats = incidents.aggregate(
        open_incidents=Count('id', filter=Q(is_incident_finish=False)),
        closed_incidents=Count('id', filter=Q(is_incident_finish=True)),
        open_last_week=Count(
            'id',
            filter=Q(is_incident_finish=False, insert_date__gte=last_week),
        ),
        closed_last_week=Count(
            'id',
            filter=Q(is_incident_finish=True, update_date__gte=last_week),
        ),
    )

    sla_percentage = 0

    closed_recent = (
        incidents.filter(
            is_incident_finish=True,
            insert_date__gte=last_week,
        )
        .select_related('incident_type')
    )

    total = stats['closed_last_week']

    if total:
        sla_ok_count = sum(
            1
            for i in closed_recent
            if not i.is_sla_avr_expired and not i.is_sla_rvr_expired
        )

        sla_percentage = round(sla_ok_count / total * 100, 1)
        if sla_percentage.is_integer():
            sla_percentage = int(sla_percentage)

    context = {
        'user': user,
        **stats,
        'sla_percentage': sla_percentage,
    }

    return render(request, 'users/user_detail.html', context)


@login_required
@role_required()
def work_schedule(request: HttpRequest, user_id: int):
    user = get_object_or_404(
        User.objects.select_related('work_schedule'),
        pk=user_id,
        is_active=True
    )

    schedule = getattr(user, 'work_schedule', None)

    if schedule is None:
        schedule = WorkSchedule(user=user)

    if (
        not request.user.is_superuser
        and not request.user.is_staff
        and request.user != user
    ):
        messages.error(
            request,
            'Данная страница доступна только персоналу'
        )
        return redirect(reverse(settings.LOGIN_URL))

    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            return redirect('users:user_detail', user_id=user.id)
        else:
            for _, errors in form.errors.items():
                for error in set(errors):
                    messages.error(request, error)
    else:
        form = WorkScheduleForm(instance=schedule)

    return render(
        request,
        'users/work_schedule_form.html',
        {'user_obj': user, 'form': form}
    )
