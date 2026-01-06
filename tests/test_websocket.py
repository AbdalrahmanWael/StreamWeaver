"""Tests for WebSocket transport."""

import pytest

# Skip all tests if fastapi is not available
pytest.importorskip("fastapi")

from streamweaver import StreamWeaver
from streamweaver.integrations.websocket import WebSocketStreamHandler, WEBSOCKET_AVAILABLE


pytestmark = pytest.mark.skipif(
    not WEBSOCKET_AVAILABLE,
    reason="FastAPI not installed"
)


class TestWebSocketStreamHandler:
    """Tests for WebSocketStreamHandler class."""

    def test_init(self):
        """Test handler initialization."""
        weaver = StreamWeaver()
        handler = WebSocketStreamHandler(
            weaver,
            ping_interval=30,
            ping_timeout=10,
        )
        
        assert handler.weaver is weaver
        assert handler.ping_interval == 30
        assert handler.ping_timeout == 10
        assert handler.connection_count == 0

    def test_register_message_handler(self):
        """Test registering a message handler."""
        weaver = StreamWeaver()
        handler = WebSocketStreamHandler(weaver)
        
        async def my_handler(session_id, data):
            pass
        
        handler.register_message_handler("custom_type", my_handler)
        
        assert "custom_type" in handler._message_handlers
        assert handler._message_handlers["custom_type"] is my_handler

    def test_connected_sessions_initially_empty(self):
        """Test that connected sessions is empty initially."""
        weaver = StreamWeaver()
        handler = WebSocketStreamHandler(weaver)
        
        assert handler.connected_sessions == []
        assert handler.connection_count == 0

    def test_parse_sse_to_json(self):
        """Test parsing SSE format to JSON."""
        weaver = StreamWeaver()
        handler = WebSocketStreamHandler(weaver)
        
        sse_data = 'id: abc-123\nevent: message\ndata: {"type": "step_progress", "message": "Test"}\n\n'
        
        result = handler._parse_sse_to_json(sse_data)
        
        assert result is not None
        assert result["type"] == "step_progress"
        assert result["message"] == "Test"

    def test_parse_sse_invalid_returns_none(self):
        """Test that invalid SSE returns None."""
        weaver = StreamWeaver()
        handler = WebSocketStreamHandler(weaver)
        
        result = handler._parse_sse_to_json("not valid sse")
        
        assert result is None

    def test_parse_sse_invalid_json_returns_none(self):
        """Test that invalid JSON in SSE returns None."""
        weaver = StreamWeaver()
        handler = WebSocketStreamHandler(weaver)
        
        sse_data = 'data: {not valid json}\n\n'
        
        result = handler._parse_sse_to_json(sse_data)
        
        assert result is None


class TestWebSocketIntegration:
    """Integration tests for WebSocket handling."""
    
    @pytest.mark.asyncio
    async def test_send_to_nonexistent_session(self):
        """Test sending to a session that's not connected."""
        weaver = StreamWeaver()
        await weaver.initialize()
        
        handler = WebSocketStreamHandler(weaver)
        
        result = await handler.send_to_session("nonexistent", {"type": "test"})
        
        assert result is False
        
        await weaver.shutdown()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_session(self):
        """Test disconnecting a session that's not connected."""
        weaver = StreamWeaver()
        await weaver.initialize()
        
        handler = WebSocketStreamHandler(weaver)
        
        result = await handler.disconnect_session("nonexistent")
        
        assert result is False
        
        await weaver.shutdown()

    @pytest.mark.asyncio
    async def test_broadcast_to_empty(self):
        """Test broadcasting when no sessions are connected."""
        weaver = StreamWeaver()
        await weaver.initialize()
        
        handler = WebSocketStreamHandler(weaver)
        
        count = await handler.broadcast({"type": "announcement"})
        
        assert count == 0
        
        await weaver.shutdown()
