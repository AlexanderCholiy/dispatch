from django.urls import path

from . import views

app_name = 'max'

urlpatterns = [
    path(
        'incidents/<int:incident_id>/',
        views.notify_max_incident,
        name='incident_notification',
    ),
]
