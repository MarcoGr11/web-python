"""
ASGI config for the Galactic Artifact Auction project.

Exposes the ASGI callable as a module-level variable named ``application``.
Routes plain HTTP requests to Django's views and WebSocket connections to
Django Channels consumers defined in ``auctions.routing``.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

import auctions.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(auctions.routing.websocket_urlpatterns)),
    }
)
