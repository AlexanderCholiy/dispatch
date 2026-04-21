from django.apps import AppConfig


class EmailsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'emails'
    verbose_name = 'Почта'

    def ready(self):
        import emails.signals  # noqa: F401
