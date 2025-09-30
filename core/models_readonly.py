from django.core.exceptions import PermissionDenied
from django.db import models


class ReadOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied(
            f'QuerySet {self.model.__name__} является read-only. '
            'Массовое обновление запрещено.'
        )

    def delete(self):
        raise PermissionDenied(
            f'QuerySet {self.model.__name__} является read-only. '
            'Массовое удаление запрещено.'
        )

    def bulk_create(self, objs, **kwargs):
        raise PermissionDenied(
            f'QuerySet {self.model.__name__} является read-only. '
            'Bulk create запрещён.'
        )


class ReadOnlyManager(models.Manager):
    def get_queryset(self):
        return ReadOnlyQuerySet(self.model, using=self._db)

    def create(self, **kwargs):
        raise PermissionDenied(
            f'Manager {self.model.__name__} является read-only. '
            'Создание запрещено.'
        )

    def get_or_create(self, **kwargs):
        raise PermissionDenied(
            f'Manager {self.model.__name__} является read-only. '
            'get_or_create запрещён.'
        )

    def update_or_create(self, **kwargs):
        raise PermissionDenied(
            f'Manager {self.model.__name__} является read-only. '
            'update_or_create запрещён.'
        )

    def bulk_create(self, objs, **kwargs):
        raise PermissionDenied(
            f'Manager {self.model.__name__} является read-only. '
            'Bulk create запрещён.'
        )


class ReadOnlyModel(models.Model):
    read_only_monitoring = True

    objects = ReadOnlyManager()

    class Meta:
        abstract = True
        managed = False

    def save(self, *args, **kwargs):
        raise PermissionDenied(
            f'Модель {self.__class__.__name__} является read-only. '
            'Сохранение запрещено.'
        )

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            f'Модель {self.__class__.__name__} является read-only. '
            'Удаление запрещено.'
        )
