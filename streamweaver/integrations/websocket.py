"""
WebSocket transport for StreamWeaver.

Provides an alternative to SSE using WebSockets for bidirectional communication.
"""

import asyncio
import contextlib
import json
import logging
from typing import Any, Callable, Optional

from ..core.filters import EventFilter
from ..core.service import StreamWeaver

logger = logging.getLogger(__name__)

# Try to import FastAPI WebSocket support
try:
    from fastapi import WebSocket, WebSocketDisconnect
    from starlette.websockets import WebSocketState

    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.debug("FastAPI not installed - WebSocket support unavailable")


class WebSocketStreamHandler:
    """
    Handles WebSocket connections for streaming events.

    Provides the same event delivery as SSE but with bidirectional communication
    support for future features like user decisions during workflows.
    """

    def __init__(
        self,
        weaver: StreamWeaver,
        ping_interval: int = 30,
        ping_timeout: int = 10,
    ):
        """
        Initialize WebSocket handler.

        Args:
            weaver: StreamWeaver instance.
            ping_interval: Seconds between ping messages.
            ping_timeout: Seconds to wait for pong response.
        """
        if not WEBSOCKET_AVAILABLE:
            raise ImportError(
                "FastAPI is required for WebSocket support. "
                "Install with: pip install streamweaver[fastapi]"
            )

        self.weaver = weaver
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self._active_connections: dict[str, WebSocket] = {}
        self._message_handlers: dict[str, Callable] = {}

    def register_message_handler(
        self,
        message_type: str,
        handler: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """
        Register a handler for incoming WebSocket messages.

        Args:
            message_type: The type field in incoming messages.
            handler: Async function(session_id, data) to handle messages.
        """
        self._message_handlers[message_type] = handler
        logger.debug(f"Registered WebSocket handler for message type: {message_type}")

    async def handle_connection(
        self,
        websocket: "WebSocket",
        session_id: str,
        last_event_id: Optional[str] = None,
        event_filter: Optional[EventFilter] = None,
    ) -> None:
        """
        Handle a WebSocket connection for a session.

        Args:
            websocket: The WebSocket connection.
            session_id: The session to stream.
            last_event_id: Optional for replay support.
            event_filter: Optional filter for events.
        """
        await websocket.accept()
        self._active_connections[session_id] = websocket

        logger.info(f"WebSocket connected for session {session_id}")

        # Get stream generator
        try:
            stream_gen = await self.weaver.get_stream_response(
                session_id,
                last_event_id=last_event_id,
                event_filter=event_filter,
            )
        except ValueError as e:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close(code=1008, reason=str(e))
            return

        # Start background tasks
        receive_task = asyncio.create_task(self._receive_messages(websocket, session_id))
        send_task = asyncio.create_task(self._send_events(websocket, session_id, stream_gen))
        ping_task = asyncio.create_task(self._ping_loop(websocket, session_id))

        try:
            # Wait for any task to complete
            done, pending = await asyncio.wait(
                [receive_task, send_task, ping_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {e}")
        finally:
            self._active_connections.pop(session_id, None)

            if websocket.client_state != WebSocketState.DISCONNECTED:
                with contextlib.suppress(Exception):
                    await websocket.close()

            logger.info(f"WebSocket disconnected for session {session_id}")

    async def _send_events(
        self,
        websocket: "WebSocket",
        session_id: str,
        stream_gen,
    ) -> None:
        """Send events from the stream to the WebSocket."""
        try:
            async for sse_data in stream_gen:
                # Parse SSE format and convert to JSON
                event_data = self._parse_sse_to_json(sse_data)
                if event_data:
                    await websocket.send_json(event_data)

                    # Check if workflow completed
                    if event_data.get("type") == "workflow_completed":
                        break

        except WebSocketDisconnect:
            logger.debug(f"WebSocket disconnected during send for {session_id}")
            raise
        except Exception as e:
            logger.error(f"Error sending WebSocket events: {e}")
            raise

    async def _receive_messages(
        self,
        websocket: "WebSocket",
        session_id: str,
    ) -> None:
        """Receive and handle incoming WebSocket messages."""
        try:
            while True:
                data = await websocket.receive_json()
                message_type = data.get("type", "unknown")

                handler = self._message_handlers.get(message_type)
                if handler:
                    try:
                        await handler(session_id, data)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"Handler error: {str(e)}",
                            }
                        )
                else:
                    logger.debug(f"No handler for message type: {message_type}")

        except WebSocketDisconnect:
            logger.debug(f"WebSocket disconnected during receive for {session_id}")
            raise
        except Exception as e:
            logger.error(f"Error receiving WebSocket messages: {e}")
            raise

    async def _ping_loop(
        self,
        websocket: "WebSocket",
        session_id: str,
    ) -> None:
        """Send periodic pings to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(self.ping_interval)

                # Send application-level ping (WebSocket protocol ping is automatic)
                await websocket.send_json(
                    {
                        "type": "ping",
                        "session_id": session_id,
                    }
                )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Ping error for session {session_id}: {e}")
            raise

    def _parse_sse_to_json(self, sse_data: str) -> Optional[dict[str, Any]]:
        """Parse SSE format to JSON dict."""
        try:
            # Extract data line from SSE format
            # Format: "id: xxx\nevent: message\ndata: {...}\n\n"
            for line in sse_data.strip().split("\n"):
                if line.startswith("data: "):
                    json_str = line[6:]  # Remove "data: " prefix
                    return json.loads(json_str)
            return None
        except Exception as e:
            logger.error(f"Error parsing SSE to JSON: {e}")
            return None

    async def send_to_session(
        self,
        session_id: str,
        message: dict[str, Any],
    ) -> bool:
        """
        Send a message to a specific session's WebSocket.

        Args:
            session_id: Target session.
            message: JSON-serializable message.

        Returns:
            True if sent, False if session not connected.
        """
        websocket = self._active_connections.get(session_id)
        if websocket is None:
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Error sending to session {session_id}: {e}")
            return False

    async def broadcast(self, message: dict[str, Any]) -> int:
        """
        Broadcast a message to all connected sessions.

        Args:
            message: JSON-serializable message.

        Returns:
            Number of sessions the message was sent to.
        """
        sent_count = 0
        for session_id in list(self._active_connections.keys()):
            if await self.send_to_session(session_id, message):
                sent_count += 1
        return sent_count

    async def disconnect_session(self, session_id: str, reason: str = "Server disconnect") -> bool:
        """
        Disconnect a session's WebSocket.

        Args:
            session_id: Session to disconnect.
            reason: Reason for disconnection.

        Returns:
            True if disconnected, False if not connected.
        """
        websocket = self._active_connections.pop(session_id, None)
        if websocket is None:
            return False

        try:
            await websocket.close(code=1000, reason=reason)
            return True
        except Exception:
            return False

    @property
    def connected_sessions(self) -> list[str]:
        """Get list of currently connected session IDs."""
        return list(self._active_connections.keys())

    @property
    def connection_count(self) -> int:
        """Get number of active WebSocket connections."""
        return len(self._active_connections)
