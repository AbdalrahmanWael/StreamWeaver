"""
Framework integrations for StreamWeaver.
"""

from .fastapi import create_lifespan, create_streaming_app, setup_streaming_routes

# Optional WebSocket support
try:
    from .websocket import WebSocketStreamHandler

    __all__ = [
        "setup_streaming_routes",
        "create_streaming_app",
        "create_lifespan",
        "WebSocketStreamHandler",
    ]
except ImportError:
    __all__ = [
        "setup_streaming_routes",
        "create_streaming_app",
        "create_lifespan",
    ]
