"""Tests for event replay functionality."""

import time

import pytest

from streamweaver import StreamEvent, StreamEventType
from streamweaver.core.replay import EventBuffer, SessionEventBuffers


class TestEventBuffer:
    """Tests for EventBuffer class."""

    def test_add_event(self):
        """Test adding events to buffer."""
        buffer = EventBuffer(max_size=10)

        event = StreamEvent(
            event_type=StreamEventType.WORKFLOW_STARTED,
            session_id="test-1",
            timestamp=time.time(),
            message="Test event",
        )

        buffer.add(event)

        assert len(buffer) == 1
        assert buffer.get_latest_event_id() == event.event_id

    def test_buffer_overflow(self):
        """Test that old events are removed when buffer is full."""
        buffer = EventBuffer(max_size=3)
        events = []

        for i in range(5):
            event = StreamEvent(
                event_type=StreamEventType.STEP_PROGRESS,
                session_id="test-1",
                timestamp=time.time() + i,
                message=f"Event {i}",
            )
            buffer.add(event)
            events.append(event)

        # Buffer should only have last 3 events
        assert len(buffer) == 3

        # First two events should not be in index
        assert events[0].event_id not in buffer._event_index
        assert events[1].event_id not in buffer._event_index

        # Last three should be there
        assert events[2].event_id in buffer._event_index
        assert events[3].event_id in buffer._event_index
        assert events[4].event_id in buffer._event_index

    def test_get_events_after(self):
        """Test replaying events after a specific event ID."""
        buffer = EventBuffer(max_size=10)
        events = []

        for i in range(5):
            event = StreamEvent(
                event_type=StreamEventType.STEP_PROGRESS,
                session_id="test-1",
                timestamp=time.time() + i,
                message=f"Event {i}",
            )
            buffer.add(event)
            events.append(event)

        # Get events after event 2 (should return events 3 and 4)
        replay_events = buffer.get_events_after(events[2].event_id)

        assert len(replay_events) == 2
        assert replay_events[0].event_id == events[3].event_id
        assert replay_events[1].event_id == events[4].event_id

    def test_get_events_after_unknown_id(self):
        """Test replay with unknown event ID returns empty list."""
        buffer = EventBuffer(max_size=10)

        event = StreamEvent(
            event_type=StreamEventType.WORKFLOW_STARTED,
            session_id="test-1",
            timestamp=time.time(),
        )
        buffer.add(event)

        replay_events = buffer.get_events_after("unknown-id")

        assert len(replay_events) == 0

    def test_get_all_events(self):
        """Test getting all buffered events."""
        buffer = EventBuffer(max_size=10)

        for i in range(3):
            event = StreamEvent(
                event_type=StreamEventType.STEP_PROGRESS,
                session_id="test-1",
                timestamp=time.time() + i,
            )
            buffer.add(event)

        all_events = buffer.get_all_events()

        assert len(all_events) == 3

    def test_clear(self):
        """Test clearing the buffer."""
        buffer = EventBuffer(max_size=10)

        for _i in range(3):
            event = StreamEvent(
                event_type=StreamEventType.STEP_PROGRESS,
                session_id="test-1",
                timestamp=time.time(),
            )
            buffer.add(event)

        cleared = buffer.clear()

        assert cleared == 3
        assert len(buffer) == 0
        assert buffer.get_latest_event_id() is None


class TestSessionEventBuffers:
    """Tests for SessionEventBuffers manager."""

    @pytest.mark.asyncio
    async def test_get_or_create_buffer(self):
        """Test getting or creating a buffer for a session."""
        buffers = SessionEventBuffers(buffer_size=50)

        buffer1 = await buffers.get_or_create_buffer("session-1")
        buffer2 = await buffers.get_or_create_buffer("session-1")

        assert buffer1 is buffer2
        assert buffers.session_count == 1

    @pytest.mark.asyncio
    async def test_add_event(self):
        """Test adding events through the manager."""
        buffers = SessionEventBuffers(buffer_size=50)

        event = StreamEvent(
            event_type=StreamEventType.WORKFLOW_STARTED,
            session_id="session-1",
            timestamp=time.time(),
        )

        await buffers.add_event("session-1", event)

        buffer = await buffers.get_or_create_buffer("session-1")
        assert len(buffer) == 1

    @pytest.mark.asyncio
    async def test_get_events_after(self):
        """Test getting events for replay through the manager."""
        buffers = SessionEventBuffers(buffer_size=50)
        events = []

        for i in range(3):
            event = StreamEvent(
                event_type=StreamEventType.STEP_PROGRESS,
                session_id="session-1",
                timestamp=time.time() + i,
            )
            await buffers.add_event("session-1", event)
            events.append(event)

        replay = await buffers.get_events_after("session-1", events[0].event_id)

        assert len(replay) == 2

    @pytest.mark.asyncio
    async def test_clear_session(self):
        """Test clearing a session's buffer."""
        buffers = SessionEventBuffers(buffer_size=50)

        for _i in range(3):
            event = StreamEvent(
                event_type=StreamEventType.STEP_PROGRESS,
                session_id="session-1",
                timestamp=time.time(),
            )
            await buffers.add_event("session-1", event)

        cleared = await buffers.clear_session("session-1")

        assert cleared == 3
        assert buffers.session_count == 0

    @pytest.mark.asyncio
    async def test_get_buffer_stats(self):
        """Test getting buffer statistics."""
        buffers = SessionEventBuffers(buffer_size=100)

        for _i in range(5):
            event = StreamEvent(
                event_type=StreamEventType.STEP_PROGRESS,
                session_id="session-1",
                timestamp=time.time(),
            )
            await buffers.add_event("session-1", event)

        stats = await buffers.get_buffer_stats("session-1")

        assert stats["size"] == 5
        assert stats["max_size"] == 100

    @pytest.mark.asyncio
    async def test_nonexistent_session_stats(self):
        """Test stats for a session that doesn't exist."""
        buffers = SessionEventBuffers(buffer_size=100)

        stats = await buffers.get_buffer_stats("nonexistent")

        assert stats["size"] == 0
        assert stats["max_size"] == 100
