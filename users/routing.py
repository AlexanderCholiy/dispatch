from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/presence/', consumers.PresenceConsumer.as_asgi()),
]
