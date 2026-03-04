from django.urls import path

from . import views

app_name = 'incidents'

urlpatterns = [
    path('', views.index, name='index'),
    path(
        'incidents/<int:incident_id>/',
        views.incident_detail,
        name='incident_detail'
    ),
    path(
        'incidents/move-emails/',
        views.confirm_move_emails,
        name='confirm_move_emails'
    ),
    path('incidents/create/', views.create_incident, name='create'),
    path(
        'incidents/<int:incident_id>/emails/new/',
        views.new_email,
        name='new_email'
    ),
    path(
        'incidents/<int:incident_id>/emails/reply/<int:reply_email_id>/',
        views.new_email,
        name='email_reply'
    ),
    path(
        'incidents/<int:incident_id>/emails/notify-operator/',
        views.notify_operator,
        name='notify_operator'
    ),
    path(
        'incidents/<int:incident_id>/emails/notify-avr-contractor/',
        views.notify_avr_contractor,
        name='notify_avr_contractor'
    ),
    path(
        'incidents/<int:incident_id>/emails/notify-rvr-contractor/',
        views.notify_rvr_contractor,
        name='notify_rvr_contractor'
    ),
    path(
        'incidents/<int:incident_id>/emails/notify-incident-closed/',
        views.notify_incident_closed,
        name='notify_incident_closed'
    ),
]
