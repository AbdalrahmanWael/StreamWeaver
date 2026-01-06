"""
Event replay support for StreamWeaver.

Enables clients to reconnect and resume from where they left off
using SSE Last-Event-ID.
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .events import StreamEvent

logger = logging.getLogger(__name__)


@dataclass
class EventBuffer:
    """
    Ring buffer for storing recent events per session.

    Enables event replay when clients reconnect with Last-Event-ID.
    Uses a deque for O(1) operations on both ends.
    """

    max_size: int = 100
    _buffer: deque[StreamEvent] = field(default_factory=deque)
    _event_index: dict[str, int] = field(default_factory=dict)  # event_id -> position
    _position_counter: int = 0

    def __post_init__(self):
        self._buffer = deque(maxlen=self.max_size)
        self._event_index = {}
        self._position_counter = 0

    def add(self, event: StreamEvent) -> None:
        """
        Add an event to the buffer.

        If the buffer is full, the oldest event is automatically removed.
        """
        # If buffer is at capacity, remove oldest event from index
        if len(self._buffer) >= self.max_size and self._buffer:
            oldest = self._buffer[0]
            self._event_index.pop(oldest.event_id, None)

        self._buffer.append(event)
        self._event_index[event.event_id] = self._position_counter
        self._position_counter += 1
        logger.debug(f"Buffered event {event.event_id} (buffer size: {len(self._buffer)})")

    def get_events_after(self, last_event_id: str) -> list[StreamEvent]:
        """
        Get all events that occurred after the given event ID.

        Args:
            last_event_id: The Last-Event-ID from the client reconnection.

        Returns:
            List of events that occurred after the given ID, in order.
            Empty list if the event ID is not found (too old or invalid).
        """
        if last_event_id not in self._event_index:
            logger.warning(f"Event ID {last_event_id} not found in buffer - may be too old")
            return []

        target_position = self._event_index[last_event_id]
        result = []

        for event in self._buffer:
            event_position = self._event_index.get(event.event_id)
            if event_position is not None and event_position > target_position:
                result.append(event)

        logger.info(f"Replaying {len(result)} events after {last_event_id}")
        return result

    def get_all_events(self) -> list[StreamEvent]:
        """Get all buffered events in order."""
        return list(self._buffer)

    def get_latest_event_id(self) -> Optional[str]:
        """Get the ID of the most recent event, if any."""
        if self._buffer:
            return self._buffer[-1].event_id
        return None

    def clear(self) -> int:
        """
        Clear all events from the buffer.

        Returns:
            Number of events cleared.
        """
        count = len(self._buffer)
        self._buffer.clear()
        self._event_index.clear()
        # Don't reset position counter to avoid ID collisions
        logger.debug(f"Cleared {count} events from buffer")
        return count

    def __len__(self) -> int:
        return len(self._buffer)


class SessionEventBuffers:
    """
    Manages event buffers for multiple sessions.

    Thread-safe access to per-session event buffers.
    """

    def __init__(self, buffer_size: int = 100):
        """
        Initialize the session event buffers.

        Args:
            buffer_size: Maximum events to store per session.
        """
        self.buffer_size = buffer_size
        self._buffers: dict[str, EventBuffer] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_buffer(self, session_id: str) -> EventBuffer:
        """Get or create a buffer for a session."""
        async with self._lock:
            if session_id not in self._buffers:
                self._buffers[session_id] = EventBuffer(max_size=self.buffer_size)
                logger.debug(f"Created event buffer for session {session_id}")
            return self._buffers[session_id]

    async def add_event(self, session_id: str, event: StreamEvent) -> None:
        """Add an event to a session's buffer."""
        buffer = await self.get_or_create_buffer(session_id)
        buffer.add(event)

    async def get_events_after(self, session_id: str, last_event_id: str) -> list[StreamEvent]:
        """Get events after the given ID for a session."""
        async with self._lock:
            buffer = self._buffers.get(session_id)
            if buffer is None:
                return []
            return buffer.get_events_after(last_event_id)

    async def clear_session(self, session_id: str) -> int:
        """Clear and remove buffer for a session."""
        async with self._lock:
            buffer = self._buffers.pop(session_id, None)
            if buffer is not None:
                return buffer.clear()
            return 0

    async def get_buffer_stats(self, session_id: str) -> dict[str, int]:
        """Get statistics for a session's buffer."""
        async with self._lock:
            buffer = self._buffers.get(session_id)
            if buffer is None:
                return {"size": 0, "max_size": self.buffer_size}
            return {
                "size": len(buffer),
                "max_size": buffer.max_size,
            }

    @property
    def session_count(self) -> int:
        """Number of sessions with active buffers."""
        return len(self._buffers)
