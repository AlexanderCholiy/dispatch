from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone
from rest_framework import serializers

from incidents.constants import (
    END_STATUS_NAME,
    GENERATION_STATUS_NAME,
    NOTIFIED_CONTRACTOR_STATUS_NAME,
    NOTIFIED_OP_END_STATUS_NAME,
    NOTIFY_CONTRACTOR_STATUS_NAME,
)
from incidents.models import Incident
from ts.models import PoleContractorEmail

from .utils import conversion_utc_datetime


class IncidentReportSerializer(serializers.ModelSerializer):
    base_station = serializers.CharField(
        source='base_station.bs_name', read_only=True)
    pole = serializers.CharField(source='pole.pole', read_only=True)
    pole_latitude = serializers.FloatField(
        source='pole.pole_latitude', read_only=True)
    pole_longtitude = serializers.FloatField(
        source='pole.pole_latitude', read_only=True)
    address = serializers.CharField(source='pole.address', read_only=True)
    incident_type = serializers.CharField(
        source='incident_type.name', read_only=True)
    region_ru = serializers.CharField(
        source='pole.region.region_ru', read_only=True
    )
    vendor = serializers.CharField(
        source='pole.avr_contractor.contractor_name', read_only=True)

    registration_method = serializers.SerializerMethodField()
    last_status = serializers.SerializerMethodField()
    is_transfer_to_avr = serializers.SerializerMethodField()
    transfer_timestamp_to_avr = serializers.SerializerMethodField()
    is_vendor_sla_expired = serializers.SerializerMethodField()
    vendor_emails = serializers.SerializerMethodField()
    operators = serializers.SerializerMethodField()
    vendor_deadline = serializers.SerializerMethodField()
    incident_datetime = serializers.SerializerMethodField()
    incident_finish_datetime = serializers.SerializerMethodField()
    operator_group = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = (
            'id',
            'code',
            'incident_datetime',
            'incident_type',
            'is_vendor_sla_expired',
            'vendor_deadline',
            'is_incident_finish',
            'incident_finish_datetime',
            'last_status',
            'is_transfer_to_avr',
            'transfer_timestamp_to_avr',
            'base_station',
            'operator_group',
            'operators',
            'pole',
            'region_ru',
            'address',
            'pole_latitude',
            'pole_longtitude',
            'vendor',
            'vendor_emails',
            'registration_method',
            'categories',
        )

    def get_registration_method(self, obj: Incident):
        return 'Автоматически из почты' if obj.is_auto_incident else (
            'Вручную через диспетчера'
        )

    def get_last_status(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return
        return obj.prefetched_statuses[-1].status.name

    def get_is_transfer_to_avr(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return
        for status_history in obj.prefetched_statuses:
            if status_history.status.name == DEFAULT_NOTIFIED_AVR_STATUS_NAME:
                return True
        return False

    def get_transfer_timestamp_to_avr(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return
        for status_history in obj.prefetched_statuses:
            if status_history.status.name == DEFAULT_NOTIFIED_AVR_STATUS_NAME:
                return conversion_utc_datetime(status_history.insert_date)
        return

    def get_vendor_emails(self, obj: Incident):
        if obj.pole and obj.pole.avr_contractor:
            emails = PoleContractorEmail.objects.filter(
                pole=obj.pole,
                contractor=obj.pole.avr_contractor
            ).values_list('email__email', flat=True).distinct()
            return ', '.join(sorted(emails)) if emails else None
        return

    def get_operator_group(self, obj: Incident):
        if obj.base_station:
            return ', '.join(set(
                [op.operator_group for op in obj.base_station.operator.all()]
            ))
        return

    def get_operators(self, obj: Incident):
        if obj.base_station:
            return ', '.join(
                [op.operator_name for op in obj.base_station.operator.all()]
            )
        return

    def get_vendor_deadline(self, obj: Incident):
        """Дедлайн SLA для подрядчика"""
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
            or not obj.incident_type
            or not obj.incident_type.sla_deadline
        ):
            return

        start_timestamp: Optional[datetime] = None

        for status_history in obj.prefetched_statuses:
            if (
                status_history.status.name == DEFAULT_NOTIFIED_AVR_STATUS_NAME
                and not start_timestamp
            ):
                start_timestamp = status_history.insert_date
                break

        deadline = conversion_utc_datetime(
            start_timestamp + timedelta(minutes=obj.incident_type.sla_deadline)
        ) if start_timestamp else None

        return deadline

    def get_is_vendor_sla_expired(self, obj: Incident):
        """
        Просрочен ли SLA в промежутке между статусом "Передано подрядчику" и
        одним из "Уведомили о закрытии", "На генерации НБ", "Закрыт".
        """
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
            or not obj.incident_type
            or not obj.incident_type.sla_deadline
        ):
            return

        start_timestamp: Optional[datetime] = None
        finish_timestamp: Optional[datetime] = None

        for status_history in obj.prefetched_statuses:
            if (
                status_history.status.name in (
                    NOTIFIED_CONTRACTOR_STATUS_NAME,
                    NOTIFY_CONTRACTOR_STATUS_NAME,
                )
                and not start_timestamp
            ):
                start_timestamp = status_history.insert_date
            elif (
                status_history.status.name in (
                    NOTIFIED_OP_END_STATUS_NAME,
                    GENERATION_STATUS_NAME,
                    END_STATUS_NAME,
                )
                and not finish_timestamp
            ):
                finish_timestamp = status_history.insert_date
            elif start_timestamp and finish_timestamp:
                break

        if not start_timestamp:
            return

        deadline = (
            start_timestamp + timedelta(minutes=obj.incident_type.sla_deadline)
        )

        if finish_timestamp:
            return finish_timestamp > deadline

        return timezone.now() > deadline

    def get_incident_datetime(self, obj: Incident):
        return conversion_utc_datetime(obj.incident_date)

    def get_incident_finish_datetime(self, obj: Incident):
        if not obj.incident_finish_date:
            return
        return conversion_utc_datetime(obj.incident_finish_date)

    def get_categories(self, obj: Incident):
        categories = obj.categories.all()
        if categories:
            return ', '.join(set(
                [cat.name for cat in categories]
            ))
        return
