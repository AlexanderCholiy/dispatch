from django.db.models import Model


class WithoutMigrationsRouter:
    """
    Роутер для CRUD операций в базе данных сетевых компаний.
    Миграции и любые изменения схемы запрещены.
    """
    energy_db = 'energy'
    energy_apps = {'energy'}

    def db_for_read(self, model: Model, **hints):
        """
        Чтение из energy, если модель помечена как energy-модель
        """
        if model._meta.app_label in self.energy_apps:
            return self.energy_db
        return None

    def db_for_write(self, model: Model, **hints):
        """Запись в БД разрешены."""
        if model._meta.app_label in self.energy_apps:
            return self.energy_db
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Запрещаем миграции на energy базе."""
        if app_label in self.energy_apps:
            return db != self.energy_db
        return None

    def allow_relation(self, obj1: Model, obj2: Model, **hints):
        """Разрешаем отношения между моделями из любой базы."""
        if (
            obj1._meta.app_label in self.energy_apps
            or obj2._meta.app_label in self.energy_apps
        ):
            return True
        return None
