from django.urls import path

from .consumers import RandomNumberConsumer

websocket_urlpatterns = [
    path('ws/random/', RandomNumberConsumer.as_asgi()),
]
