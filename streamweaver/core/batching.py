"""
Event batching for StreamWeaver.

Reduces overhead for high-frequency events by batching multiple events
into a single SSE message.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .events import StreamEvent

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for event batching."""

    enabled: bool = False
    max_batch_size: int = 10
    max_batch_delay_ms: int = 50
    # Event types that should never be batched (sent immediately)
    immediate_types: List[str] = field(
        default_factory=lambda: [
            "workflow_completed",
            "error",
            "workflow_interruption",
        ]
    )


class EventBatcher:
    """
    Batches multiple events for efficient delivery.

    Events are accumulated and sent either when:
    1. The batch reaches max_batch_size
    2. The batch timeout expires
    3. An immediate event type is received
    """

    def __init__(
        self,
        session_id: str,
        config: Optional[BatchConfig] = None,
        on_batch_ready: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the event batcher.

        Args:
            session_id: The session this batcher belongs to.
            config: Batching configuration.
            on_batch_ready: Callback when a batch is ready to send.
        """
        self.session_id = session_id
        self.config = config or BatchConfig()
        self.on_batch_ready = on_batch_ready

        self._batch: List[StreamEvent] = []
        self._batch_start_time: Optional[float] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def batch_size(self) -> int:
        """Current number of events in the batch."""
        return len(self._batch)

    async def add(self, event: StreamEvent) -> Optional[str]:
        """
        Add an event to the batch.

        Args:
            event: The event to add.

        Returns:
            SSE-formatted string if batch should be flushed, None otherwise.
        """
        if self._closed:
            return None

        if not self.config.enabled:
            # Batching disabled - return event immediately
            return event.to_sse_format()

        # Check if this event type should be sent immediately
        event_type_value = (
            event.event_type.value if hasattr(event.event_type, "value") else event.event_type
        )
        if event_type_value in self.config.immediate_types:
            # Flush current batch first, then return this event
            result = await self._flush_and_format()
            result += event.to_sse_format()
            return result

        should_flush = False
        async with self._lock:
            self._batch.append(event)

            if self._batch_start_time is None:
                self._batch_start_time = time.time()
                # Start the timeout task
                self._start_flush_timer()

            # Check if batch is full
            if len(self._batch) >= self.config.max_batch_size:
                should_flush = True

        # Flush outside lock to avoid deadlock
        if should_flush:
            return await self._flush_and_format()

        return None

    def _start_flush_timer(self) -> None:
        """Start the flush timer task."""
        if self._flush_task is not None and not self._flush_task.done():
            return

        async def flush_timer():
            try:
                await asyncio.sleep(self.config.max_batch_delay_ms / 1000.0)
                sse_data = await self._flush_and_format()
                if sse_data and self.on_batch_ready:
                    self.on_batch_ready(sse_data)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in flush timer: {e}")

        self._flush_task = asyncio.create_task(flush_timer())

    async def _flush_and_format(self) -> str:
        """Flush the current batch and format as SSE."""
        async with self._lock:
            if not self._batch:
                return ""

            events = self._batch.copy()
            self._batch.clear()
            self._batch_start_time = None

            if self._flush_task and not self._flush_task.done():
                self._flush_task.cancel()
                self._flush_task = None

        return self._format_batch(events)

    def _format_batch(self, events: List[StreamEvent]) -> str:
        """Format a batch of events as SSE."""
        if len(events) == 1:
            return events[0].to_sse_format()

        # Multiple events - send as array
        batch_data = [event.to_dict() for event in events]
        last_event = events[-1]

        return (
            f"id: {last_event.event_id}\n" f"event: batch\n" f"data: {json.dumps(batch_data)}\n\n"
        )

    async def flush(self) -> str:
        """
        Force flush the current batch.

        Returns:
            SSE-formatted string of batched events.
        """
        return await self._flush_and_format()

    async def close(self) -> str:
        """
        Close the batcher and flush remaining events.

        Returns:
            SSE-formatted string of remaining events.
        """
        self._closed = True
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        return await self._flush_and_format()


class BatcherPool:
    """
    Manages event batchers for multiple sessions.
    """

    def __init__(self, default_config: Optional[BatchConfig] = None):
        """
        Initialize the batcher pool.

        Args:
            default_config: Default batching configuration for new batchers.
        """
        self.default_config = default_config or BatchConfig()
        self._batchers: dict[str, EventBatcher] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        session_id: str,
        config: Optional[BatchConfig] = None,
        on_batch_ready: Optional[Callable[[str], None]] = None,
    ) -> EventBatcher:
        """Get or create a batcher for a session."""
        async with self._lock:
            if session_id not in self._batchers:
                self._batchers[session_id] = EventBatcher(
                    session_id=session_id,
                    config=config or self.default_config,
                    on_batch_ready=on_batch_ready,
                )
            return self._batchers[session_id]

    async def remove(self, session_id: str) -> Optional[str]:
        """Remove and close a batcher, returning any pending events."""
        async with self._lock:
            batcher = self._batchers.pop(session_id, None)
            if batcher:
                return await batcher.close()
        return None

    async def close_all(self) -> None:
        """Close all batchers."""
        async with self._lock:
            for batcher in self._batchers.values():
                await batcher.close()
            self._batchers.clear()
