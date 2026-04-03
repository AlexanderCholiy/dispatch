from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path(
        'ws/incidents/comments/<int:incident_id>/',
        consumers.CommentConsumer.as_asgi()
    ),
]
