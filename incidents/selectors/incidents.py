from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from emails.models import EmailMessage, EmailReference
from incidents.models import Incident, IncidentStatusHistory


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

        return get_object_or_404(
            Incident.objects.prefetch_related(
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
            ),
            id=incident_id
        )
