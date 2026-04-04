from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.throttling import ScopedRateThrottle

from api.filters import CommentFilter
from api.pagination import CommentPagination
from api.permissions import UserPermission
from api.serializers.comment import CommentSerializer
from incidents.models import Comment
from users.models import Roles, User


class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления комментариями к инцидентам.

    Требования:
    - Только авторизованные пользователи (через JWT).
    - При создании автор подставляется автоматически из токена.
    - Редактирование/удаление разрешено только автору комментария.
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, UserPermission]
    pagination_class = CommentPagination

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'comment_request'

    filter_backends = (
        DjangoFilterBackend,
        filters.OrderingFilter,
    )
    filterset_class = CommentFilter

    ordering_fields = ['created_at', 'id']
    ordering = ['-created_at', '-id']

    def get_queryset(self):
        user: User = self.request.user
        qs = (
            Comment.objects
            .select_related('incident', 'author')
            .filter(incident__code__isnull=False)
        )
        if user.role == Roles.DISPATCH or user.is_superuser or user.is_staff:
            return qs
        return qs.filter(
            Q(author=user) | Q(author__role=Roles.DISPATCH)
        )

    def perform_create(self, serializer: CommentSerializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer: CommentSerializer):
        instance: Comment = serializer.instance
        user: User = self.request.user
        if not (instance.author == user or user.is_superuser or user.is_staff):
            raise PermissionDenied(
                'Вы можете редактировать только свои комментарии.'
            )
        super().perform_update(serializer)

    def perform_destroy(self, instance: Comment):
        user: User = self.request.user
        if not (
            instance.author == user
            or user.is_superuser
            or user.is_staff
        ):
            raise PermissionDenied(
                'Вы можете удалять только свои комментарии.'
            )
        super().perform_destroy(instance)
