from django.db.models import F
from rest_framework import serializers

from energy.models import (
    Appeal,
    AppealAttr,
    AppealStatus,
    AttrType,
    Claim,
    ClaimAttr,
    ClaimStatus,
)


class AttrTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttrType
        fields = ('attribute_id', 'name', 'description')


class ClaimAttrSerializer(serializers.ModelSerializer):
    attr_name = serializers.CharField(source='attr_type.name', read_only=True)

    class Meta:
        model = ClaimAttr
        fields = ('attr_name', 'text', 'created_at')


class AppealAttrSerializer(serializers.ModelSerializer):
    attr_name = serializers.CharField(source='attr_type.name', read_only=True)

    class Meta:
        model = AppealAttr
        fields = ('attr_name', 'text', 'created_at')


class ClaimStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimStatus
        fields = ('name', 'created_at', 'date')


class AppealStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppealStatus
        fields = ('name', 'created_at', 'date')


class ClaimSerializer(serializers.ModelSerializer):
    declarant_name = serializers.CharField(source='declarant.name')
    company_name = serializers.CharField(source='company.name')

    attrs = ClaimAttrSerializer(
        source='claim_attrs', many=True, read_only=True
    )

    last_status = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = (
            'id',
            'number',
            'declarant_name',
            'company_name',
            'last_status',
            'attrs',
        )

    def get_last_status(self, obj):
        if hasattr(obj, 'ordered_statuses'):
            status = obj.ordered_statuses[0] if obj.ordered_statuses else None
        else:
            status = (
                obj.claim_statuses
                .order_by(
                    F('date').desc(nulls_last=True),
                    F('created_at').desc(),
                    F('id').desc()
                )
                .first()
            )

        if status:
            return ClaimStatusSerializer(status).data
        return None


class AppealSerializer(serializers.ModelSerializer):
    declarant_name = serializers.CharField(source='declarant.name')
    company_name = serializers.CharField(source='company.name')

    attrs = AppealAttrSerializer(
        source='appeal_attrs', many=True, read_only=True
    )

    last_status = serializers.SerializerMethodField()

    class Meta:
        model = Appeal
        fields = (
            'id',
            'number',
            'declarant_name',
            'company_name',
            'last_status',
            'attrs',
        )

    def get_last_status(self, obj):
        if hasattr(obj, 'ordered_statuses'):
            status = obj.ordered_statuses[0] if obj.ordered_statuses else None
        else:
            status = (
                obj.appeal_statuses
                .order_by(
                    F('date').desc(nulls_last=True),
                    F('created_at').desc(),
                    F('id').desc()
                )
                .first()
            )

        if status:
            return AppealStatusSerializer(status).data
        return None
