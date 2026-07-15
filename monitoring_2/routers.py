from django.db.models import Model


class WithoutMigrationsRouter:
    """
    Роутер для CRUD операций в базе данных сетевых компаний.
    Миграции и любые изменения схемы запрещены.
    """
    monitoring_2_db = 'monitoring_2'
    monitoring_2_apps = {'monitoring_2'}

    def db_for_read(self, model: Model, **hints):
        """
        Чтение из monitoring 2.0, если модель помечена как monitoring_2-модель
        """
        if model._meta.app_label in self.monitoring_2_apps:
            return self.monitoring_2_db
        return None

    def db_for_write(self, model: Model, **hints):
        """Запись в БД разрешены."""
        if model._meta.app_label in self.monitoring_2_apps:
            return self.monitoring_2_db
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Запрещаем миграции на energy базе."""
        if app_label in self.monitoring_2_apps:
            return db != self.monitoring_2_db
        return None

    def allow_relation(self, obj1: Model, obj2: Model, **hints):
        """Разрешаем отношения между моделями из любой базы."""
        if (
            obj1._meta.app_label in self.monitoring_2_apps
            or obj2._meta.app_label in self.monitoring_2_apps
        ):
            return True
        return None
