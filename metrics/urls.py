from django.urls import path

from . import views

app_name = 'metrics'

urlpatterns = [
    path(
        '',
        views.grafana_general_statistics_dashboard,
        name='dispatch_general_stats'
    ),
    path(
        'map/',
        views.grafana_general_map_dashboard,
        name='dispatch_general_map'
    ),
]
