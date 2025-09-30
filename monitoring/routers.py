from django.db.models import Model


class ReadOnlyRouter:
    """
    Роутер для чтения данных из базы MSSQL мониторинга.
    Любые попытки записи, миграций или изменений данных запрещены.
    """

    read_only_db = 'monitoring'

    def db_for_read(self, model: Model, **hints):
        """
        Все операции чтения идут в read-only базу, если модель предназначена
        для мониторинга.
        """
        if getattr(model, 'read_only_monitoring', False):
            return self.read_only_db
        return 'default'

    def db_for_write(self, model: Model, **hints):
        """Запрещаем любые операции записи."""
        if getattr(model, 'read_only_monitoring', False):
            return None
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Запрещаем миграции на read-only базе."""
        if db == self.read_only_db:
            return False
        return None

    def allow_relation(self, obj1: Model, obj2: Model, **hints):
        """Разрешаем отношения между моделями из любой базы."""
        allowed_dbs = {'default', self.read_only_db}
        if obj1._state.db in allowed_dbs and obj2._state.db in allowed_dbs:
            return True
        return None

    def allow_delete(self, obj: Model, **hints):
        """Запрещаем удаление в read-only базе."""
        if getattr(obj, 'read_only_monitoring', False):
            return False
        return True
