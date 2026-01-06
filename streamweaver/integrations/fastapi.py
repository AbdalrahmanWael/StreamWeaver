"""
FastAPI integration for StreamWeaver.
"""

import gzip
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from ..core.metrics import PROMETHEUS_AVAILABLE
from ..core.service import StreamWeaver

logger = logging.getLogger(__name__)


def create_lifespan(weaver: StreamWeaver) -> Callable:
    """
    Create a lifespan context manager for FastAPI.

    Usage:
        weaver = StreamWeaver()
        app = FastAPI(lifespan=create_lifespan(weaver))
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        await weaver.initialize()
        yield
        # Shutdown
        await weaver.shutdown()

    return lifespan


def setup_streaming_routes(
    app: FastAPI,
    weaver: StreamWeaver,
    prefix: str = "",
    enable_websocket: bool = False,
    enable_metrics_endpoint: bool = False,
) -> None:
    """
    Add streaming routes to FastAPI app.

    Args:
        app: FastAPI application.
        weaver: StreamWeaver instance.
        prefix: Optional URL prefix for routes.
        enable_websocket: Enable WebSocket endpoint.
        enable_metrics_endpoint: Enable /metrics endpoint.
    """

    @app.get(f"{prefix}/stream/{{session_id}}")
    async def stream(
        request: Request,
        session_id: str,
        last_event_id: Optional[str] = Query(None, alias="lastEventId"),
    ):
        """
        Get SSE stream for a session.

        Supports reconnection via Last-Event-ID header or query parameter.
        """
        session = await weaver.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check for Last-Event-ID header (takes precedence)
        header_last_event_id = request.headers.get("Last-Event-ID")
        effective_last_event_id = header_last_event_id or last_event_id

        # Get stream generator
        stream_gen = await weaver.get_stream_response(
            session_id,
            last_event_id=effective_last_event_id,
        )

        # Check if compression is enabled and client supports it
        accept_encoding = request.headers.get("Accept-Encoding", "")
        use_compression = weaver.config.enable_compression and "gzip" in accept_encoding

        if use_compression:
            # Wrap generator with compression
            async def compressed_stream():
                async for chunk in stream_gen:
                    if len(chunk) >= weaver.config.compression_threshold:
                        compressed = gzip.compress(chunk.encode("utf-8"))
                        yield compressed
                    else:
                        yield chunk.encode("utf-8")

            return StreamingResponse(
                compressed_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream",
                    "Content-Encoding": "gzip",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control, Last-Event-ID",
                    "Access-Control-Expose-Headers": "Content-Encoding",
                    "X-Accel-Buffering": "no",
                },
            )

        return StreamingResponse(
            stream_gen,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control, Last-Event-ID",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get(f"{prefix}/stream/{{session_id}}/status")
    async def get_stream_status(session_id: str):
        """Get current status of a session."""
        session = await weaver.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        queue_stats = weaver.get_queue_stats(session_id)

        return {
            "sessionId": session.session_id,
            "status": session.status,
            "progress": f"{session.completed_steps}/{session.total_steps}",
            "currentStep": session.current_step,
            "createdAt": session.created_at,
            "lastActivity": session.last_activity,
            "queue": queue_stats,
        }

    @app.post(f"{prefix}/stream/{{session_id}}/close")
    async def close_stream(session_id: str, request_data: dict[str, Any] = None):
        """Close an active stream."""
        session = await weaver.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        request_data = request_data or {}
        reason = request_data.get("reason", "Client requested closure")
        success = await weaver.close_stream(session_id, reason)

        if success:
            return {
                "success": True,
                "message": f"Stream closed for session {session_id}",
                "sessionId": session_id,
                "reason": reason,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to close stream")

    @app.get(f"{prefix}/stream/{{session_id}}/replay")
    async def get_replay_events(
        session_id: str,
        after: str = Query(..., description="Event ID to replay from"),
    ):
        """Get events for replay after a specific event ID."""
        session = await weaver.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        events = await weaver.get_replay_events(session_id, after)

        return {
            "sessionId": session_id,
            "eventCount": len(events),
            "events": [event.to_dict() for event in events],
        }

    # WebSocket endpoint (optional)
    if enable_websocket:
        try:
            from fastapi import WebSocket as FastAPIWebSocket

            from .websocket import WebSocketStreamHandler

            ws_handler = WebSocketStreamHandler(weaver)

            @app.websocket(f"{prefix}/ws/{{session_id}}")
            async def websocket_stream(
                websocket: FastAPIWebSocket,
                session_id: str,
            ):
                """WebSocket endpoint for streaming."""
                # Get last event ID from query params
                last_event_id = websocket.query_params.get("lastEventId")

                await ws_handler.handle_connection(
                    websocket,
                    session_id,
                    last_event_id=last_event_id,
                )

            logger.info("WebSocket endpoint enabled")

        except ImportError:
            logger.warning("WebSocket support not available")

    # Metrics endpoint (optional)
    if enable_metrics_endpoint and PROMETHEUS_AVAILABLE:
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

            @app.get(f"{prefix}/metrics")
            async def metrics():
                """Prometheus metrics endpoint."""
                return Response(
                    content=generate_latest(),
                    media_type=CONTENT_TYPE_LATEST,
                )

            logger.info("Metrics endpoint enabled")

        except ImportError:
            logger.warning("Prometheus client not available for metrics endpoint")

    logger.info(f"Streaming routes registered with prefix '{prefix}'")


def create_streaming_app(
    weaver: StreamWeaver,
    title: str = "StreamWeaver API",
    enable_websocket: bool = False,
    enable_metrics: bool = False,
) -> FastAPI:
    """
    Create a FastAPI app with streaming routes.

    Args:
        weaver: StreamWeaver instance.
        title: API title.
        enable_websocket: Enable WebSocket endpoint.
        enable_metrics: Enable metrics endpoint.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title=title,
        lifespan=create_lifespan(weaver),
    )

    setup_streaming_routes(
        app,
        weaver,
        enable_websocket=enable_websocket,
        enable_metrics_endpoint=enable_metrics,
    )

    return app
