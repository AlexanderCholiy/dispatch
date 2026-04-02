from rest_framework import permissions
from rest_framework.request import Request

from users.models import Roles, User


class UserPermission(permissions.BasePermission):

    def has_permission(self, request: Request, view) -> bool:
        user: User | None = request.user
        if not user or not user.is_authenticated:
            return False

        user_role = user.role

        allowed_roles = [Roles.DISPATCH, Roles.ENERGY, Roles.USER]
        return user_role in allowed_roles

    def has_object_permission(self, request: Request, view, obj) -> bool:
        user: User = request.user
        author: User | None = getattr(obj, 'author', None)

        if author == user or user.is_superuser or user.is_staff:
            return True

        return False
