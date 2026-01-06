"""Tests for event batching."""

import asyncio
import pytest
import time

from streamweaver import StreamEvent, StreamEventType
from streamweaver.core.batching import BatchConfig, EventBatcher, BatcherPool


def create_event(
    event_type=StreamEventType.STEP_PROGRESS,
    message="Test",
) -> StreamEvent:
    """Helper to create test events."""
    return StreamEvent(
        event_type=event_type,
        session_id="test-session",
        timestamp=time.time(),
        message=message,
    )


class TestBatchConfig:
    """Tests for BatchConfig."""

    def test_default_config(self):
        """Test default batch configuration."""
        config = BatchConfig()

        assert config.enabled is False
        assert config.max_batch_size == 10
        assert config.max_batch_delay_ms == 50
        assert "workflow_completed" in config.immediate_types
        assert "error" in config.immediate_types

    def test_custom_config(self):
        """Test custom batch configuration."""
        config = BatchConfig(
            enabled=True,
            max_batch_size=5,
            max_batch_delay_ms=100,
            immediate_types=["error"],
        )

        assert config.enabled is True
        assert config.max_batch_size == 5
        assert config.max_batch_delay_ms == 100
        assert config.immediate_types == ["error"]


class TestEventBatcher:
    """Tests for EventBatcher."""

    @pytest.mark.asyncio
    async def test_disabled_batching_returns_immediately(self):
        """Test that disabled batching returns events immediately."""
        config = BatchConfig(enabled=False)
        batcher = EventBatcher("session-1", config)

        event = create_event()
        result = await batcher.add(event)

        assert result is not None
        assert "event: message" in result
        assert event.event_id in result

    @pytest.mark.asyncio
    async def test_batching_accumulates_events(self):
        """Test that events are accumulated when batching is enabled."""
        config = BatchConfig(enabled=True, max_batch_size=5)
        batcher = EventBatcher("session-1", config)

        # Add first event - should not return anything yet
        event1 = create_event(message="Event 1")
        result = await batcher.add(event1)
        assert result is None

        # Add second event - still accumulating
        event2 = create_event(message="Event 2")
        result = await batcher.add(event2)
        assert result is None

        assert batcher.batch_size == 2

    @pytest.mark.asyncio
    async def test_batch_flush_on_size(self):
        """Test that batch is flushed when max size is reached."""
        config = BatchConfig(enabled=True, max_batch_size=3)
        batcher = EventBatcher("session-1", config)

        await batcher.add(create_event(message="Event 1"))
        await batcher.add(create_event(message="Event 2"))
        result = await batcher.add(create_event(message="Event 3"))

        assert result is not None
        assert "event: batch" in result

    @pytest.mark.asyncio
    async def test_immediate_event_flushes_batch(self):
        """Test that immediate event types flush the batch."""
        config = BatchConfig(enabled=True, max_batch_size=10)
        batcher = EventBatcher("session-1", config)

        await batcher.add(create_event(message="Event 1"))
        await batcher.add(create_event(message="Event 2"))

        # Add workflow_completed which should flush
        result = await batcher.add(create_event(event_type=StreamEventType.WORKFLOW_COMPLETED))

        assert result is not None
        # Should contain the batched events plus the immediate event
        assert "workflow_completed" in result

    @pytest.mark.asyncio
    async def test_manual_flush(self):
        """Test manually flushing the batch."""
        config = BatchConfig(enabled=True, max_batch_size=10)
        batcher = EventBatcher("session-1", config)

        await batcher.add(create_event(message="Event 1"))
        await batcher.add(create_event(message="Event 2"))

        result = await batcher.flush()

        assert result is not None
        assert batcher.batch_size == 0

    @pytest.mark.asyncio
    async def test_close_flushes_remaining(self):
        """Test that closing the batcher flushes remaining events."""
        config = BatchConfig(enabled=True, max_batch_size=10)
        batcher = EventBatcher("session-1", config)

        await batcher.add(create_event(message="Event 1"))
        await batcher.add(create_event(message="Event 2"))

        result = await batcher.close()

        assert result is not None
        assert batcher.batch_size == 0

    @pytest.mark.asyncio
    async def test_single_event_not_batched_format(self):
        """Test that a single event uses regular SSE format."""
        config = BatchConfig(enabled=True, max_batch_size=10)
        batcher = EventBatcher("session-1", config)

        await batcher.add(create_event())

        result = await batcher.flush()

        # Single event should use "event: message" not "event: batch"
        assert "event: message" in result


class TestBatcherPool:
    """Tests for BatcherPool."""

    @pytest.mark.asyncio
    async def test_get_or_create(self):
        """Test getting or creating a batcher."""
        pool = BatcherPool()

        batcher1 = await pool.get_or_create("session-1")
        batcher2 = await pool.get_or_create("session-1")
        batcher3 = await pool.get_or_create("session-2")

        assert batcher1 is batcher2
        assert batcher1 is not batcher3

    @pytest.mark.asyncio
    async def test_remove_and_flush(self):
        """Test removing a batcher flushes pending events."""
        config = BatchConfig(enabled=True, max_batch_size=10)
        pool = BatcherPool(default_config=config)

        batcher = await pool.get_or_create("session-1")
        await batcher.add(create_event())

        result = await pool.remove("session-1")

        assert result is not None
        assert "event: message" in result

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self):
        """Test removing a batcher that doesn't exist."""
        pool = BatcherPool()

        result = await pool.remove("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_close_all(self):
        """Test closing all batchers."""
        pool = BatcherPool()

        await pool.get_or_create("session-1")
        await pool.get_or_create("session-2")
        await pool.get_or_create("session-3")

        await pool.close_all()

        # Pool should be empty
        assert len(pool._batchers) == 0

    @pytest.mark.asyncio
    async def test_custom_config_per_session(self):
        """Test using custom config for specific sessions."""
        default_config = BatchConfig(enabled=False)
        custom_config = BatchConfig(enabled=True, max_batch_size=5)
        pool = BatcherPool(default_config=default_config)

        batcher1 = await pool.get_or_create("session-1")
        batcher2 = await pool.get_or_create("session-2", config=custom_config)

        assert batcher1.config.enabled is False
        assert batcher2.config.enabled is True
        assert batcher2.config.max_batch_size == 5
