from django.urls import path

from .consumers import UserNotificationConsumer

websocket_urlpatterns = [
    path('ws/notifications/', UserNotificationConsumer.as_asgi()),
]
