import time

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import default_storage
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from .constants import (
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_USER_EMAIL_LEN,
    MAX_USER_PASSWORD_LEN,
    MAX_USER_ROLE_LEN,
    MAX_USER_USERNAME_LEN,
    PASSWORD_HELP_TEXT,
    USERNAME_HELP_TEXT,
    SUBFOLDER_AVATAR_DIR,
)
from .validators import (
    username_format_validators,
    validate_pending_email,
    validate_pending_password,
    validate_pending_username,
    validate_user_email,
    validate_user_username
)


class Roles(models.TextChoices):
    GUEST = ('guest', 'Гость')
    USER = ('user', 'Пользователь')
    DISPATCH = ('dispatch', 'Диспетчер')


class User(AbstractUser):
    email = models.EmailField(
        'Email',
        unique=True,
        max_length=MAX_USER_EMAIL_LEN,
        help_text='Введите адрес электронной почты',
        validators=[validate_user_email]
    )
    username = models.CharField(
        'Имя пользователя',
        max_length=MAX_USER_USERNAME_LEN,
        unique=True,
        validators=username_format_validators + [validate_user_username],
        help_text=USERNAME_HELP_TEXT,
    )
    avatar = models.ImageField(
        'Аватар',
        upload_to=SUBFOLDER_AVATAR_DIR,
        blank=True,
        null=True,
        help_text='Загрузите аватар пользователя в формате JPG или PNG',
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)
        ],
    )
    role = models.CharField(
        'Роль',
        max_length=MAX_USER_ROLE_LEN,
        choices=Roles.choices,
        default=Roles.GUEST,
        help_text='Выберите роль пользователя',
    )
    date_of_birth = models.DateField(
        'Дата рождения',
        null=True,
        blank=True,
        help_text='Формат: ГГГГ-ММ-ДД'
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username

    @property
    def temporary_username(self):
        """
        Генерирует уникальное временное имя с timestamp.
        Нужно для безопасной смены email, при создании временного пользователя.
        """
        return f'{self.username}__temp_{int(time.time())}_{self.pk}'

    def delete(self, *args, **kwargs):
        if self.avatar:
            self.avatar.delete(save=False)
        super().delete(*args, **kwargs)

    def clean(self):
        super().clean()
        validate_user_username(self.username, self)
        validate_user_email(self.email, self)

    def save(self, *args, **kwargs) -> None:
        is_new = self.pk is None
        self.full_clean()

        try:
            old_avatar = User.objects.get(pk=self.pk).avatar
        except User.DoesNotExist:
            old_avatar = None

        super().save(*args, **kwargs)

        if old_avatar and old_avatar != self.avatar:
            if default_storage.exists(old_avatar.name):
                default_storage.delete(old_avatar.name)

        if is_new:
            WorkSchedule.objects.create(user=self)


class WorkSchedule(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='work_schedule',
        verbose_name='Пользователь'
    )
    monday = models.BooleanField('Понедельник', default=True)
    tuesday = models.BooleanField('Вторник', default=True)
    wednesday = models.BooleanField('Среда', default=True)
    thursday = models.BooleanField('Четверг', default=True)
    friday = models.BooleanField('Пятница', default=True)
    saturday = models.BooleanField('Суббота', default=False)
    sunday = models.BooleanField('Воскресенье', default=False)

    start_time = models.TimeField('Начало', default='09:00')
    end_time = models.TimeField('Конец', default='18:00')

    class Meta:
        verbose_name = 'Расписание рабочего времени'
        verbose_name_plural = 'Расписания рабочего времени'

    def get_fields(self):
        return {
            'Пн': self.monday,
            'Вт': self.tuesday,
            'Ср': self.wednesday,
            'Чт': self.thursday,
            'Пт': self.friday,
            'Сб': self.saturday,
            'Вс': self.sunday,
        }

    @property
    def is_working(self) -> bool:
        return any(
            (
                self.monday,
                self.tuesday,
                self.wednesday,
                self.thursday,
                self.friday,
                self.saturday,
                self.sunday,
            )
        )

    @property
    def is_working_now(self) -> bool:
        now = timezone.localtime()
        weekday = now.weekday()
        current_time = now.time()

        days = {
            0: self.monday,
            1: self.tuesday,
            2: self.wednesday,
            3: self.thursday,
            4: self.friday,
            5: self.saturday,
            6: self.sunday,
        }

        if not days.get(weekday, False):
            return False

        if self.start_time == self.end_time:
            return True

        return self.start_time <= current_time <= self.end_time

    def __str__(self):
        is_work = 'работает' if self.is_working_now else 'не работает'
        return f'{self.user.username}: {is_work}'


class PendingUser(models.Model):
    username = models.CharField(
        'Имя пользователя',
        max_length=MAX_USER_USERNAME_LEN,
        unique=True,
        validators=username_format_validators + [validate_pending_username],
        help_text=USERNAME_HELP_TEXT,
    )
    email = models.EmailField(
        'Почта',
        unique=True,
        max_length=MAX_USER_EMAIL_LEN,
        validators=[validate_pending_email],
        help_text='Введите адрес электронной почты',
    )

    password = models.CharField(
        max_length=MAX_USER_PASSWORD_LEN,
        validators=[validate_pending_password],
        help_text=PASSWORD_HELP_TEXT,
    )

    last_login = models.DateTimeField('Дата регистрации', default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'регистрация пользователя'
        verbose_name_plural = 'Регистрация пользоватей'

    def __str__(self) -> str:
        return self.username

    @property
    def original_username(self):
        """
        Извлекает оригинальное имя пользователя.
        Нужно для поиска по username в модели User.
        """
        parts = self.username.rsplit('__temp_', 1)
        return parts[0] if len(parts) > 1 else self.username

    def clean(self):
        super().clean()
        validate_pending_username(self.username, self)
        validate_pending_email(self.email, self)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_email_field_name(self) -> str:
        return 'email'

    @property
    def is_expired(self) -> bool:
        """
        Данный метод нужен, чтобы удалять пользователей давно не
        подтверждавших регистрацию.
        """
        return (
            timezone.now() - self.last_login
            > settings.REGISTRATION_ACCESS_TOKEN_LIFETIME
        )
