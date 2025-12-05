import os

from core.constants import PUBLIC_SUBFOLDER_NAME

MAX_USER_USERNAME_LEN = 150
MIN_USER_USERNAME_LEN = 4
MAX_USER_EMAIL_LEN = 254
MAX_USER_PASSWORD_LEN = 128
MIN_USER_PASSWORD_LEN = 8
MAX_USER_ROLE_LEN = 16

USERS_PER_PAGE = 9
PAGE_SIZE_USERS_CHOICES = [USERS_PER_PAGE, 15, 30]

MAX_USER_USERNAME_DISPLAY_LEN = MAX_USER_USERNAME_LEN - 20
MIN_USER_AGE = 18
MAX_USER_AGE = 120
SUBFOLDER_AVATAR_DIR = os.path.join(PUBLIC_SUBFOLDER_NAME, 'users')

USERNAME_HELP_TEXT = (
    'Имя пользователя должно содержать минимум '
    f'{MIN_USER_USERNAME_LEN} символов.\n'
    'Разрешены: латинские буквы, цифры, точка, нижнее подчёркивание '
    'или тире.'
)
PASSWORD_HELP_TEXT = (
    f'Пароль должен содержать минимум {MIN_USER_PASSWORD_LEN} символов.\n'
    'Не может состоять только из цифр.\n'
    'Не должен быть похож на имя пользователя.\n'
    'Не должен быть слишком простым.'
)

ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png']
