"""
Main streaming service that ties everything together.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from .backpressure import BackpressurePolicy
from .batching import BatchConfig
from .events import EventVisibility, StreamEvent, StreamEventType
from .filters import EventFilter
from .generator import StreamGenerator
from .metrics import StreamWeaverMetrics, init_metrics
from .session import InMemorySessionStore, SessionStore

logger = logging.getLogger(__name__)


class StreamWeaverConfig(BaseModel):
    """Configuration for StreamWeaver."""

    # Session settings
    session_timeout: int = Field(default=3600, description="Session timeout in seconds")
    max_concurrent_streams: int = Field(default=1000, description="Maximum concurrent streams")

    # Stream settings
    enable_heartbeat: bool = Field(default=True, description="Enable heartbeat events")
    heartbeat_interval: int = Field(default=30, description="Seconds between heartbeats")

    # Queue settings
    queue_size: int = Field(default=1000, description="Maximum events per queue")
    backpressure_policy: BackpressurePolicy = Field(
        default=BackpressurePolicy.DROP_OLDEST,
        description="Policy for queue overflow",
    )

    # Replay settings
    enable_replay: bool = Field(default=True, description="Enable event replay")
    event_buffer_size: int = Field(default=100, description="Events to buffer for replay")

    # Batching settings
    enable_batching: bool = Field(default=False, description="Enable event batching")
    batch_size: int = Field(default=10, description="Maximum events per batch")
    batch_delay_ms: int = Field(default=50, description="Max delay before flush")

    # Observability settings
    enable_metrics: bool = Field(default=False, description="Enable Prometheus metrics")
    metrics_prefix: str = Field(default="streamweaver", description="Metric name prefix")

    # Compression settings
    enable_compression: bool = Field(default=False, description="Enable gzip compression")
    compression_threshold: int = Field(default=1024, description="Min bytes before compressing")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")


class StreamWeaver:
    """Main streaming service for agentic workflows."""

    def __init__(
        self,
        config: Optional[StreamWeaverConfig] = None,
        session_store: Optional[SessionStore] = None,
    ):
        """
        Initialize StreamWeaver.

        Args:
            config: Configuration options.
            session_store: Custom session storage backend.
        """
        self.config = config or StreamWeaverConfig()
        self.session_store = session_store or InMemorySessionStore(self.config.session_timeout)
        self.stream_generator = StreamGenerator(
            session_store=self.session_store,
            queue_size=self.config.queue_size,
            backpressure_policy=self.config.backpressure_policy,
            heartbeat_interval=self.config.heartbeat_interval,
            event_buffer_size=self.config.event_buffer_size,
        )
        self.streaming_tasks: dict[str, asyncio.Task] = {}
        self.metrics: Optional[StreamWeaverMetrics] = None

        # Initialize batching config
        self._batch_config = BatchConfig(
            enabled=self.config.enable_batching,
            max_batch_size=self.config.batch_size,
            max_batch_delay_ms=self.config.batch_delay_ms,
        )

    async def initialize(self) -> None:
        """Initialize the streaming service."""
        if isinstance(self.session_store, InMemorySessionStore):
            await self.session_store.initialize()

        # Initialize metrics if enabled
        if self.config.enable_metrics:
            self.metrics = init_metrics(
                enabled=True,
                prefix=self.config.metrics_prefix,
            )

        logger.info("StreamWeaver initialized")

    async def register_session(
        self,
        session_id: str,
        user_request: str,
        context: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Register a new session."""
        context = context or {}
        await self.session_store.create_session(session_id, user_request, context, user_id)

        if self.metrics:
            self.metrics.record_session_created()

    async def get_session(self, session_id: str):
        """Get session data."""
        return await self.session_store.get_session(session_id)

    async def publish(
        self,
        session_id: str,
        event_type: StreamEventType,
        message: str = "",
        data: Optional[dict[str, Any]] = None,
        visibility: EventVisibility = EventVisibility.USER_FACING,
        **kwargs,
    ) -> bool:
        """
        Publish an event to a session.

        Args:
            session_id: Target session.
            event_type: Type of event.
            message: Human-readable message.
            data: Arbitrary event data.
            visibility: Event visibility level.
            **kwargs: Additional event fields.

        Returns:
            True if event was published, False if dropped.
        """
        event = StreamEvent(
            event_type=event_type,
            session_id=session_id,
            timestamp=time.time(),
            message=message,
            data=data,
            visibility=visibility,
            **kwargs,
        )

        # Get event type for metrics
        event_type_value = (
            event_type.value if isinstance(event_type, StreamEventType) else event_type
        )

        success = await self.stream_generator.publish_event(session_id, event)

        if self.metrics:
            if success:
                self.metrics.record_event_published(session_id, event_type_value)
            else:
                self.metrics.record_event_dropped(session_id)

        return success

    async def get_stream_response(
        self,
        session_id: str,
        last_event_id: Optional[str] = None,
        event_filter: Optional[EventFilter] = None,
    ):
        """
        Get SSE streaming response for a session.

        Args:
            session_id: The session to stream.
            last_event_id: Optional Last-Event-ID for reconnection.
            event_filter: Optional filter to apply to events.

        Returns:
            Async generator yielding SSE-formatted strings.

        Raises:
            ValueError: If session not found.
        """
        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        if self.metrics:
            self.metrics.record_stream_connected(reconnection=last_event_id is not None)

        return self.stream_generator.generate_stream(
            session_id,
            last_event_id=last_event_id,
            event_filter=event_filter,
        )

    def register_event_callback(
        self,
        session_id: str,
        callback: Callable[[StreamEvent], Awaitable[None]],
    ) -> None:
        """Register a callback for session events."""
        self.stream_generator.register_event_callback(session_id, callback)

    async def check_capacity(self) -> bool:
        """Check if capacity is available for new streams."""
        active_count = await self.session_store.get_active_count()
        return active_count < self.config.max_concurrent_streams

    async def cleanup_session_resources(self, session_id: str) -> None:
        """Clean up resources for a session."""
        logger.info(f"Cleaning up resources for session: {session_id}")
        await self.stream_generator.cleanup_queue(session_id)
        self.stream_generator.register_event_callback(session_id, None)

    async def close_stream(self, session_id: str, reason: str = "Stream closed") -> bool:
        """Close a stream and clean up resources."""
        try:
            logger.info(f"Closing stream for session {session_id}. Reason: {reason}")

            await self.stream_generator.cancel_stream(session_id)

            if session_id in self.streaming_tasks:
                task = self.streaming_tasks[session_id]
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                del self.streaming_tasks[session_id]

            await self.session_store.update_session(session_id, status="completed")
            await self.session_store.delete_session(session_id)

            await self.stream_generator.cleanup_queue(session_id)
            self.stream_generator.register_event_callback(session_id, None)

            if self.metrics:
                self.metrics.record_session_closed(reason)
                self.metrics.record_stream_disconnected(reason)

            logger.info(f"Stream closed for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error closing stream for session {session_id}: {e}")
            if self.metrics:
                self.metrics.record_error("close_stream_error")
            return False

    async def get_replay_events(
        self,
        session_id: str,
        last_event_id: str,
    ) -> list[StreamEvent]:
        """Get events for replay after reconnection."""
        return await self.stream_generator.get_replay_events(session_id, last_event_id)

    def get_queue_stats(self, session_id: str) -> dict[str, Any]:
        """Get queue statistics for a session."""
        return self.stream_generator.get_queue_stats(session_id)

    async def shutdown(self) -> None:
        """Shutdown the streaming service."""
        logger.info("Shutting down StreamWeaver")
        if isinstance(self.session_store, InMemorySessionStore):
            await self.session_store.close()
