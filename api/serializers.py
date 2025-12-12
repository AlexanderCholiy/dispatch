from rest_framework import serializers

from incidents.models import Incident
from ts.models import Region

from .utils import conversion_utc_datetime


class IncidentReportSerializer(serializers.ModelSerializer):
    base_station = serializers.CharField(
        source='base_station.bs_name', read_only=True
    )
    pole = serializers.CharField(source='pole.pole', read_only=True)
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
    avr_start_datetime = serializers.SerializerMethodField()
    avr_end_datetime = serializers.SerializerMethodField()
    avr_deadline = serializers.SerializerMethodField()
    avr_emails = serializers.SerializerMethodField()
    rvr_start_datetime = serializers.SerializerMethodField()
    rvr_end_datetime = serializers.SerializerMethodField()
    rvr_deadline = serializers.SerializerMethodField()
    incident_datetime = serializers.SerializerMethodField()
    incident_finish_datetime = serializers.SerializerMethodField()
    operator_group = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = (
            'code',
            'last_status',
            'incident_type',
            'categories',
            'incident_datetime',
            'incident_finish_datetime',
            'avr_start_datetime',
            'avr_end_datetime',
            'is_sla_avr_expired',
            'avr_deadline',
            'avr_names',
            'avr_emails',
            'rvr_start_datetime',
            'rvr_end_datetime',
            'is_sla_rvr_expired',
            'rvr_deadline',
            'pole',
            'region_ru',
            'base_station',
            'operator_group',
        )

    def get_last_status(self, obj: Incident):
        if (
            not hasattr(obj, 'prefetched_statuses')
            or not obj.prefetched_statuses
        ):
            return
        return obj.prefetched_statuses[-1].status.name

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


class StatisticReportSerializer(serializers.ModelSerializer):
    total_closed_incidents = serializers.IntegerField(read_only=True)
    total_open_incidents = serializers.IntegerField(read_only=True)
    active_contractor_incidents = serializers.IntegerField(read_only=True)

    sla_avr_expired_count = serializers.IntegerField(read_only=True)
    sla_rvr_expired_count = serializers.IntegerField(read_only=True)

    sla_avr_closed_on_time_count = serializers.IntegerField(read_only=True)
    sla_rvr_closed_on_time_count = serializers.IntegerField(read_only=True)

    sla_avr_less_than_hour = serializers.IntegerField(read_only=True)
    sla_rvr_less_than_hour = serializers.IntegerField(read_only=True)

    sla_avr_in_progress = serializers.IntegerField(read_only=True)
    sla_rvr_in_progress = serializers.IntegerField(read_only=True)

    total_incidents = serializers.SerializerMethodField()

    class Meta:
        model = Region
        fields = (
            'region_ru',
            'total_incidents',
            'total_closed_incidents',
            'total_open_incidents',
            'active_contractor_incidents',
            'sla_avr_expired_count',
            'sla_avr_closed_on_time_count',
            'sla_avr_less_than_hour',
            'sla_avr_in_progress',
            'sla_rvr_expired_count',
            'sla_rvr_closed_on_time_count',
            'sla_rvr_less_than_hour',
            'sla_rvr_in_progress',
        )

    def get_total_incidents(self, obj: Region):
        total_closed_incidents = getattr(obj, 'total_closed_incidents', 0)
        total_open_incidents = getattr(obj, 'total_open_incidents', 0)
        return total_closed_incidents + total_open_incidents
