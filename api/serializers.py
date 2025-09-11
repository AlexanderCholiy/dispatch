from rest_framework import serializers

from incidents.constants import DEFAULT_NOTIFIED_AVR_STATUS_NAME
from incidents.models import Incident

from .utils import conversion_utc_datetime


class IncidentSerializer(serializers.ModelSerializer):
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
    region = serializers.CharField(source='pole.region', read_only=True)
    vendor = serializers.CharField(
        source='pole.avr_contractor.contractor_name', read_only=True)

    registration_method = serializers.SerializerMethodField()
    last_status = serializers.SerializerMethodField()
    is_transfer_to_avr = serializers.SerializerMethodField()
    transfer_timestamp_to_avr = serializers.SerializerMethodField()
    vendor_emails = serializers.SerializerMethodField()
    operators = serializers.SerializerMethodField()
    deadline = serializers.SerializerMethodField()
    incident_datetime = serializers.SerializerMethodField()
    incident_finish_datetime = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = (
            'id',
            'code',
            'incident_datetime',
            'incident_type',
            'is_sla_expired',
            'deadline',
            'is_incident_finish',
            'incident_finish_datetime',
            'last_status',
            'is_transfer_to_avr',
            'transfer_timestamp_to_avr',
            'base_station',
            'operators',
            'pole',
            'region',
            'address',
            'pole_latitude',
            'pole_longtitude',
            'vendor',
            'vendor_emails',
            'registration_method',
        )

    def get_registration_method(self, obj: Incident):
        return 'Автоматически из почты' if obj.is_auto_incident else (
            'Вручную через диспетчера')

    def get_last_status(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return None
        return obj.prefetched_statuses[-1].status.name

    def get_is_transfer_to_avr(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return None
        for status_history in obj.prefetched_statuses:
            if status_history.status.name == DEFAULT_NOTIFIED_AVR_STATUS_NAME:
                return True
        return False

    def get_transfer_timestamp_to_avr(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return None
        for status_history in obj.prefetched_statuses:
            if status_history.status.name == DEFAULT_NOTIFIED_AVR_STATUS_NAME:
                return conversion_utc_datetime(status_history.insert_date)
        return None

    def get_vendor_emails(self, obj: Incident):
        if obj.pole and obj.pole.avr_contractor:
            return [
                email.email for email in obj.pole.avr_contractor.emails.all()
            ]
        return []

    def get_operators(self, obj: Incident):
        if obj.base_station:
            return [op.operator_name for op in obj.base_station.operator.all()]
        return []

    def get_deadline(self, obj: Incident):
        if obj.sla_deadline:
            return conversion_utc_datetime(obj.sla_deadline)
        return None

    def get_is_sla_expired(self, obj: Incident):
        return obj.is_sla_expired

    def get_incident_datetime(self, obj: Incident):
        return conversion_utc_datetime(obj.incident_date)

    def get_incident_finish_datetime(self, obj: Incident):
        if not obj.incident_finish_date:
            return None
        return conversion_utc_datetime(obj.incident_finish_date)
