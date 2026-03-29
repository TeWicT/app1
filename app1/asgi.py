"""
ASGI config for app1 project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import logging
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app1.settings')

django_asgi_app = get_asgi_application()

try:
    from webd_core.routing import websocket_urlpatterns
except Exception:
    # If this import fails, Channels will silently have no websocket routes and will return 404.
    # We log the exception to make the root cause visible in `docker compose logs`.
    logging.getLogger(__name__).exception("Failed to import websocket_urlpatterns")
    websocket_urlpatterns = []

logger = logging.getLogger("app1.websocket_debug")
logger.warning("Loaded websocket_urlpatterns: %s", [str(p.pattern) for p in websocket_urlpatterns])

ws_application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))


def _headers_to_dict(scope):
    return {
        (k.decode("latin1", errors="ignore") if isinstance(k, bytes) else str(k)): (
            v.decode("latin1", errors="ignore") if isinstance(v, bytes) else str(v)
        )
        for k, v in scope.get("headers", [])
    }


async def http_debug_app(scope, receive, send):
    path = scope.get("path", "")
    if path.startswith("/ws/"):
        headers = _headers_to_dict(scope)
        logger.warning(
            "HTTP request reached /ws path (not websocket). path=%s method=%s upgrade=%s connection=%s xfp=%s host=%s",
            path,
            scope.get("method"),
            headers.get("upgrade"),
            headers.get("connection"),
            headers.get("x-forwarded-proto"),
            headers.get("host"),
        )
    return await django_asgi_app(scope, receive, send)


async def websocket_debug_app(scope, receive, send):
    headers = _headers_to_dict(scope)
    logger.warning(
        "WS connect attempt. path=%s client=%s scheme=%s upgrade=%s connection=%s xfp=%s host=%s",
        scope.get("path"),
        scope.get("client"),
        scope.get("scheme"),
        headers.get("upgrade"),
        headers.get("connection"),
        headers.get("x-forwarded-proto"),
        headers.get("host"),
    )
    return await ws_application(scope, receive, send)


application = ProtocolTypeRouter({
    "http": http_debug_app,
    "websocket": websocket_debug_app,
})
