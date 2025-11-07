from django.urls import path

from . import views

app_name = 'incidents'

urlpatterns = [
    path('', views.index, name='index'),
    path(
        'incident/<int:incident_id>/',
        views.incident_detail,
        name='incident_detail'
    ),
]
