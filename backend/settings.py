import os
from datetime import timedelta
from logging import Filter
from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-e68v&dizcxaw&)21bcs&+5')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')
    if host.strip()
]

INTERNAL_IPS = ['127.0.0.1', 'localhost']

CSRF_TRUSTED_ORIGINS = [
    dom.strip() for dom in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if dom.strip()
]

CSRF_FAILURE_VIEW = 'core.views.csrf_failure'

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

CSRF_COOKIE_AGE = 31449600  # 1 год

SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SESSION_COOKIE_AGE = 604800  # Неделя

SESSION_SAVE_EVERY_REQUEST = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'debug_toolbar',
    'core.apps.CoreConfig',
    'users.apps.UsersConfig',
    'pages.apps.PagesConfig',
    'emails.apps.EmailsConfig',
    'ts.apps.TsConfig',
    'incidents.apps.IncidentsConfig',
    'yandex_tracker.apps.YandexTrackerConfig',
    'api.apps.ApiConfig',
    'monitoring.apps.MonitoringConfig',
    'rest_framework',
    'django_filters',
    'djoser',
    'drf_yasg',
    'axes',  # после всех приложений
    'django_cleanup.apps.CleanupConfig',  # после всех приложений
    'django_celery_results',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'backend.urls'
LOGIN_REDIRECT_URL = 'incidents:index'
LOGIN_URL = 'login'

TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'django'),
        'USER': os.getenv('POSTGRES_USER', 'django'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': int(os.getenv('DB_PORT', 5432)),
    },
    'monitoring': {
        'ENGINE': 'mssql',
        'NAME': os.getenv('MONITORING_DB_NAME', 'django'),
        'USER': os.getenv('MONITORING_DB_USER', 'django'),
        'PASSWORD': os.getenv('MONITORING_DB_PASSWORD', ''),
        'HOST': os.getenv('MONITORING_DB_HOST', 'localhost'),
        'PORT': int(os.getenv('MONITORING_DB_PORT', 1433)),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'Encrypt': 'no',
            'TrustServerCertificate': 'yes',
            'Connection Timeout': 10,
        },
    },
    'ts': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('TS_DB_NAME'),
        'USER': os.environ.get('TS_DB_USER'),
        'PASSWORD': os.environ.get('TS_DB_PASSWORD'),
        'HOST': os.environ.get('TS_DB_HOST'),
        'PORT': os.environ.get('TS_DB_PORT'),
    },
}

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_RESULT_EXTENDED = True
CELERY_TRACK_STARTED = True
CELERY_RESULT_EXPIRES = 7 * 24 * 3600  # Очистка записей

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Moscow'

# Подтверждаем задачу после выполнения.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# Максимальное количество задач, которые один процесс воркера выполнит перед
# перезапуском. Полезно для очистки памяти после долгих задач.
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
# Сколько задач воркер берёт сразу из очереди для обработки
# (предотвращает "захват" многих задач одним воркером).
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# Если задача выполняется дольше, Celery выбрасывает исключение
# SoftTimeLimitExceeded внутри задачи, которое можно поймать и корректно
# завершить обработку.
CELERY_TASK_SOFT_TIME_LIMIT = 300
# Если задача превышает это время, Celery принудительно завершает процесс,
# который её выполняет. Используется для защиты от «зависших» задач, которые
# могут блокировать воркеры.
CELERY_TASK_TIME_LIMIT = 600

CELERY_BEAT_SCHEDULE = {
    'cleanup_old_task_results': {
        'task': 'core.tasks.cleanup_old_task_results',
        'schedule': crontab(hour=0, minute=0),
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': (
            f'redis://{os.getenv("REDIS_USER", "default")}:'
            f'{os.getenv("REDIS_PASSWORD", "")}@'
            f'{os.getenv("REDIS_HOST", "localhost")}:'
            f'{os.getenv("REDIS_PORT", 6379)}/1'
        ),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 3600,
    }
}

DATABASE_ROUTERS = ['monitoring.routers.ReadOnlyRouter']

MIGRATION_MODULES = {
    'monitoring': None,
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation'
            '.UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.NumericPasswordValidator'
        ),
    },
]

LANGUAGE_CODE = 'ru-RU'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'collected_static')

STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = '/media/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

AUTH_USER_MODEL = 'users.User'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REGISTRATION_ACCESS_TOKEN_LIFETIME = timedelta(days=1)

AXES_FAILURE_LIMIT = 3

AXES_COOLOFF_TIME = timedelta(seconds=30)

AXES_LOCKOUT_TEMPLATE = 'core/429_account_locked.html'

AXES_USERNAME_FORM_FIELD = 'username'

AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']

AXES_RESET_ON_SUCCESS = True

RATELIMIT_VIEW = 'core.views.too_many_requests'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.yandex.ru')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],

    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '10000/day',
        'anon': '1000/day',
    },
    'DEFAULT_PAGINATION_CLASS': (
        'rest_framework.pagination.PageNumberPagination'
    ),
    'PAGE_SIZE': 10,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    }
}


class ServerErrorFilter(Filter):
    def filter(self, record):
        return getattr(record, 'status_code', None) == 500


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'server_error_filter': {
            '()': ServerErrorFilter,
        },
    },
    'formatters': {
        'verbose': {
            'format': '%(asctime)s | %(levelname).1s | %(name)s | %(funcName)s | %(message)s',  # noqa: E501
        },
    },
    'handlers': {
        **({'console': {
            'class': 'logging.StreamHandler',
            'level': 'WARNING',
            'formatter': 'verbose',
        }} if DEBUG else {}),
        'rotating_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'WARNING',
            'formatter': 'verbose',
            'filename': os.path.join(BASE_DIR, 'logs', 'django', 'django.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 3,
            'encoding': 'utf-8',
        },
        'rotating_500_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'verbose',
            'filename': os.path.join(BASE_DIR, 'logs', 'django', '500.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 3,
            'encoding': 'utf-8',
            'filters': ['server_error_filter'],
        },
        'rotating_celery_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'verbose',
            'filename': os.path.join(BASE_DIR, 'logs', 'celery', 'celery.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
        }
    },
    'loggers': {
        'django': {
            'handlers': [
                'rotating_file', 'console'
            ] if DEBUG else ['rotating_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': [
                'rotating_file', 'console'
            ] if DEBUG else ['rotating_500_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'celery': {
            'handlers': [
                'rotating_celery_file', 'console'
            ] if DEBUG else ['rotating_celery_file'],
            'level': 'INFO',
            'propagate': False,
        }
    },
}
