# Порядок инициализации не менять.

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from incidents import routing as incidents_routing  # noqa: E402
from notifications import routing as notifications_routing  # noqa: E402
from stats import routing as stats_routing  # noqa: E402

websocket_patterns = (
    stats_routing.websocket_urlpatterns
    + notifications_routing.websocket_urlpatterns
    + incidents_routing.websocket_urlpatterns
)

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_patterns)
    ),
})
