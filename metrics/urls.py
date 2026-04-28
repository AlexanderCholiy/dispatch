from django.urls import path

from . import views

app_name = 'metrics'

urlpatterns = [
    path('', views.grafana_general_dashboard, name='dispatch_general_stats'),
]
