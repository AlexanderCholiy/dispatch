from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from emails.models import EmailMessage, EmailReference
from incidents.models import Incident, IncidentStatusHistory
from ts.models import PoleContractorEmail, BaseStationOperator


class IncidentSelector:

    @staticmethod
    def incidents_with_email_history(incident_id: int) -> Incident:
        references_qs = (
            EmailReference.objects
            .select_related('email_msg')
            .order_by('id')
        )

        emails_qs = (
            EmailMessage.objects
            .select_related('folder', 'email_mime')
            .prefetch_related(
                Prefetch(
                    'email_references',
                    queryset=references_qs,
                    to_attr='prefetched_references'
                ),
                'email_msg_to',
                'email_msg_cc',
            )
            .order_by('email_date', 'id')
        )

        status_history_qs = (
            IncidentStatusHistory.objects
            .select_related('status', 'status__status_type')
            .order_by('-insert_date', '-id')
        )

        pole_avr_emails_qs = (
            PoleContractorEmail.objects
            .select_related('contractor', 'email')
            .order_by('contractor__contractor_name', 'email__email')
        )

        return get_object_or_404(
            Incident.objects
            .select_related(
                'incident_type',
                'incident_subtype',
                'pole',
                'pole__region',
                'pole__region__rvr_email',
                'pole__avr_contractor',
                'base_station',
            )
            .prefetch_related(
                'categories',
                Prefetch(
                    'email_messages',
                    queryset=emails_qs,
                    to_attr='all_incident_emails'
                ),
                Prefetch(
                    'status_history',
                    queryset=status_history_qs,
                    to_attr='prefetched_status_history'
                ),
                Prefetch(
                    'pole__pole_emails',
                    queryset=pole_avr_emails_qs,
                    to_attr='prefetched_pole_avr_emails'
                ),
                Prefetch(
                    'base_station__operator',
                    queryset=(
                        BaseStationOperator.objects.all()
                        .order_by('operator_group', 'operator_name')
                    ),
                    to_attr='prefetched_operators'
                ),
            ),
            id=incident_id
        )
