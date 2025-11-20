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
    )
]
