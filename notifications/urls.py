from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path(
        '<int:notification_id>/',
        views.notification_detail,
        name='notification_detail'
    ),
    path(
        'create/',
        views.NotificationCreateView.as_view(),
        name='notification_create'
    ),
    path(
        'create/incident/<int:incident_id>/',
        views.NotificationCreateFromIncidentView.as_view(),
        name='notification_create_from_incident',
    ),
]
