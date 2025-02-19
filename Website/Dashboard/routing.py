from django.urls import re_path
from .consumers import CaptureConsumer  # Import your WebSocket consumer

websocket_urlpatterns = [
    re_path(r'ws/capture_updates/$', CaptureConsumer.as_asgi()),  # Define the WebSocket URL
]