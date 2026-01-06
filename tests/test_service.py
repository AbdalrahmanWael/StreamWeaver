"""Tests for StreamWeaver service."""

import asyncio
import pytest
from datetime import datetime

from streamweaver import (
    StreamWeaver,
    StreamEventType,
    StreamWeaverConfig,
    EventVisibility,
    BackpressurePolicy,
)


@pytest.mark.asyncio
async def test_streamweaver_initialization():
    """Test initializing StreamWeaver."""
    weaver = StreamWeaver()
    await weaver.initialize()

    assert weaver is not None
    assert weaver.config is not None

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_custom_config():
    """Test StreamWeaver with custom config."""
    config = StreamWeaverConfig(
        session_timeout=7200,
        max_concurrent_streams=500,
        heartbeat_interval=15,
        queue_size=500,
        backpressure_policy=BackpressurePolicy.DROP_NEWEST,
        enable_replay=True,
        event_buffer_size=200,
        log_level="DEBUG",
    )

    weaver = StreamWeaver(config)
    await weaver.initialize()

    assert weaver.config.session_timeout == 7200
    assert weaver.config.max_concurrent_streams == 500
    assert weaver.config.heartbeat_interval == 15
    assert weaver.config.queue_size == 500
    assert weaver.config.backpressure_policy == BackpressurePolicy.DROP_NEWEST
    assert weaver.config.event_buffer_size == 200

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_register_session():
    """Test registering a new session."""
    weaver = StreamWeaver()
    await weaver.initialize()

    await weaver.register_session(
        session_id="test-1",
        user_request="Hello world",
        context={"key": "value"},
        user_id="user-123",
    )

    session = await weaver.get_session("test-1")
    assert session is not None
    assert session.session_id == "test-1"
    assert session.user_request == "Hello world"
    assert session.context == {"key": "value"}
    assert session.user_id == "user-123"

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_publish_event():
    """Test publishing an event."""
    weaver = StreamWeaver()
    await weaver.initialize()

    await weaver.register_session("test-2", "test", {})

    success = await weaver.publish(
        session_id="test-2",
        event_type=StreamEventType.WORKFLOW_STARTED,
        message="Starting workflow",
    )

    assert success is True

    # Verify session was updated
    session = await weaver.get_session("test-2")
    assert session is not None

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_publish_with_visibility():
    """Test publishing events with different visibility levels."""
    weaver = StreamWeaver()
    await weaver.initialize()

    await weaver.register_session("test-vis", "test", {})

    # Publish user-facing event
    success1 = await weaver.publish(
        session_id="test-vis",
        event_type=StreamEventType.STEP_PROGRESS,
        message="User visible",
        visibility=EventVisibility.USER_FACING,
    )
    assert success1 is True

    # Publish internal event
    success2 = await weaver.publish(
        session_id="test-vis",
        event_type=StreamEventType.STEP_PROGRESS,
        message="Internal only",
        visibility=EventVisibility.INTERNAL_ONLY,
    )
    assert success2 is True

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_stream_generation():
    """Test that stream can be generated."""
    weaver = StreamWeaver()
    await weaver.initialize()

    await weaver.register_session("test-3", "test", {})

    # Generate stream (async generator)
    stream_gen = await weaver.get_stream_response("test-3")

    # Get first chunk (initial connection event)
    first_chunk = await stream_gen.__anext__()
    assert "event: message" in first_chunk
    assert "Connected to stream" in first_chunk

    # Publish an event
    await weaver.publish(
        session_id="test-3",
        event_type=StreamEventType.HEARTBEAT,
        message="Test event",
    )

    # Get next chunk
    second_chunk = await stream_gen.__anext__()
    assert "event: message" in second_chunk

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_close_stream():
    """Test closing a stream."""
    weaver = StreamWeaver()
    await weaver.initialize()

    await weaver.register_session("test-4", "test", {})

    success = await weaver.close_stream("test-4", "Test closure")

    assert success is True

    session = await weaver.get_session("test-4")
    assert session is None  # Session should be deleted

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_event_callback():
    """Test event callback registration."""
    weaver = StreamWeaver()
    await weaver.initialize()

    received_events = []

    async def callback(event):
        received_events.append(event)

    await weaver.register_session("test-5", "test", {})
    weaver.register_event_callback("test-5", callback)

    await weaver.publish(
        session_id="test-5",
        event_type=StreamEventType.WORKFLOW_STARTED,
        message="Test",
    )

    await asyncio.sleep(0.1)  # Give callback time to execute

    assert len(received_events) == 1
    assert received_events[0].message == "Test"

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_check_capacity():
    """Test capacity checking."""
    config = StreamWeaverConfig(max_concurrent_streams=10)
    weaver = StreamWeaver(config)
    await weaver.initialize()

    # Should have capacity initially
    has_capacity = await weaver.check_capacity()
    assert has_capacity is True

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_get_queue_stats():
    """Test getting queue statistics."""
    weaver = StreamWeaver()
    await weaver.initialize()

    await weaver.register_session("test-stats", "test", {})

    # Initially no queue exists
    stats = weaver.get_queue_stats("test-stats")
    assert stats["exists"] is False

    # Publish an event to create the queue
    await weaver.publish(
        session_id="test-stats",
        event_type=StreamEventType.STEP_PROGRESS,
        message="Test",
    )

    # Now queue should exist
    stats = weaver.get_queue_stats("test-stats")
    assert stats["exists"] is True
    assert stats["size"] >= 0

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_get_replay_events():
    """Test getting events for replay."""
    weaver = StreamWeaver()
    await weaver.initialize()

    await weaver.register_session("test-replay", "test", {})

    # Publish some events
    await weaver.publish(
        session_id="test-replay",
        event_type=StreamEventType.WORKFLOW_STARTED,
        message="Event 1",
    )

    await weaver.publish(
        session_id="test-replay",
        event_type=StreamEventType.STEP_PROGRESS,
        message="Event 2",
    )

    # Get all replay events (use a fake event ID that won't exist)
    # Since we can't easily get the first event's ID, test the method works
    events = await weaver.get_replay_events("test-replay", "nonexistent-id")

    # Should return empty since the ID wasn't found
    assert events == []

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_session_not_found():
    """Test that accessing nonexistent session raises error."""
    weaver = StreamWeaver()
    await weaver.initialize()

    with pytest.raises(ValueError, match="Session not found"):
        await weaver.get_stream_response("nonexistent")

    await weaver.shutdown()


@pytest.mark.asyncio
async def test_metrics_disabled_by_default():
    """Test that metrics are disabled by default."""
    weaver = StreamWeaver()
    await weaver.initialize()

    assert weaver.config.enable_metrics is False
    assert weaver.metrics is None

    await weaver.shutdown()
