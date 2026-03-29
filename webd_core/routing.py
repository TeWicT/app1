from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Match both with and without leading slash (ASGI scope may include it depending on server/proxy).
    re_path(r"^/?ws/discussion/(?P<thread_id>\d+)/?$", consumers.DiscussionConsumer.as_asgi()),
]
