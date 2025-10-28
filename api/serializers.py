from rest_framework import serializers

from incidents.models import Incident

from .utils import conversion_utc_datetime


class IncidentReportSerializer(serializers.ModelSerializer):
    base_station = serializers.CharField(
        source='base_station.bs_name', read_only=True
    )
    pole = serializers.CharField(source='pole.pole', read_only=True)
    pole_latitude = serializers.FloatField(
        source='pole.pole_latitude', read_only=True
    )
    pole_longtitude = serializers.FloatField(
        source='pole.pole_latitude', read_only=True
    )
    address = serializers.CharField(source='pole.address', read_only=True)
    incident_type = serializers.CharField(
        source='incident_type.name', read_only=True
    )
    region_ru = serializers.CharField(
        source='pole.region.region_ru', read_only=True
    )
    avr_names = serializers.CharField(
        source='pole.avr_contractor.contractor_name', read_only=True
    )

    last_status = serializers.SerializerMethodField()
    is_transfer_to_avr = serializers.SerializerMethodField()
    avr_start_datetime = serializers.SerializerMethodField()
    avr_end_datetime = serializers.SerializerMethodField()
    avr_deadline = serializers.SerializerMethodField()
    avr_emails = serializers.SerializerMethodField()
    is_transfer_to_rvr = serializers.SerializerMethodField()
    rvr_start_datetime = serializers.SerializerMethodField()
    rvr_end_datetime = serializers.SerializerMethodField()
    rvr_deadline = serializers.SerializerMethodField()
    operators = serializers.SerializerMethodField()
    incident_datetime = serializers.SerializerMethodField()
    incident_finish_datetime = serializers.SerializerMethodField()
    operator_group = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = (
            'id',
            'code',
            'last_status',
            'incident_type',
            'categories',
            'is_auto_incident',
            'is_incident_finish',
            'incident_datetime',
            'incident_finish_datetime',
            'is_transfer_to_avr',
            'avr_start_datetime',
            'avr_end_datetime',
            'is_sla_avr_expired',
            'avr_deadline',
            'avr_names',
            'avr_emails',
            'is_transfer_to_rvr',
            'rvr_start_datetime',
            'rvr_end_datetime',
            'is_sla_rvr_expired',
            'rvr_deadline',
            'pole',
            'region_ru',
            'address',
            'pole_latitude',
            'pole_longtitude',
            'base_station',
            'operator_group',
            'operators',
        )

    def get_last_status(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return
        return obj.prefetched_statuses[-1].status.name

    def get_is_transfer_to_avr(self, obj: Incident):
        return obj.avr_start_date is not None

    def get_is_transfer_to_rvr(self, obj: Incident):
        return obj.rvr_start_date is not None

    def get_avr_start_datetime(self, obj: Incident):
        if not obj.avr_start_date:
            return
        return conversion_utc_datetime(obj.avr_start_date)

    def get_avr_end_datetime(self, obj: Incident):
        if not obj.avr_end_date:
            return
        return conversion_utc_datetime(obj.avr_end_date)

    def get_rvr_start_datetime(self, obj: Incident):
        if not obj.rvr_start_date:
            return
        return conversion_utc_datetime(obj.rvr_start_date)

    def get_rvr_end_datetime(self, obj: Incident):
        if not obj.rvr_end_date:
            return
        return conversion_utc_datetime(obj.rvr_end_date)

    def get_avr_emails(self, obj: Incident):
        if not obj.pole or not obj.pole.avr_contractor:
            return None

        emails = [
            pce.email.email
            for pce in obj.pole.pole_emails.all()
            if pce.contractor_id == obj.pole.avr_contractor_id
        ]
        return ', '.join(sorted(set(emails))) if emails else None

    def get_operator_group(self, obj: Incident):
        if not obj.base_station:
            return None
        return ', '.join({
            op.operator_group for op in obj.base_station.operator.all()
        })

    def get_operators(self, obj: Incident):
        if not obj.base_station:
            return None
        return ', '.join({
            op.operator_name for op in obj.base_station.operator.all()
        })

    def get_avr_deadline(self, obj: Incident):
        deadline = obj.sla_avr_deadline
        return conversion_utc_datetime(deadline) if deadline else None

    def get_rvr_deadline(self, obj: Incident):
        deadline = obj.sla_rvr_deadline
        return conversion_utc_datetime(deadline) if deadline else None

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
