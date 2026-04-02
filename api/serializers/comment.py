from rest_framework import serializers

from incidents.models import Comment, Incident
from users.models import Roles, User


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    incident_id = serializers.PrimaryKeyRelatedField(
        queryset=Incident.objects.all(),
        source='incident',
        write_only=True
    )
    incident_code = serializers.CharField(
        source='incident.code', read_only=True
    )
    author_id = serializers.IntegerField(
        source='author.id', read_only=True
    )
    author_role = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id',
            'incident_id',
            'incident_code',
            'author_id',
            'author_role',
            'author',
            'content',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'author_role',
            'created_at',
            'updated_at',
        ]

    def get_author_role(self, obj: Comment):
        author: User = obj.author
        role_value = author.role
        return Roles(role_value).label

    def validate_content(self, value: str):
        if not value or not value.strip():
            raise serializers.ValidationError(
                'Сообщение не может быть пустым или состоять только из '
                'пробелов.'
            )
        return value
