from django.urls import path

from .consumers import IncidentStatsConsumer

websocket_urlpatterns = [
    path('ws/incidents/stats/', IncidentStatsConsumer.as_asgi()),
]
