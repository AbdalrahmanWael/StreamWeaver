"""Tests for backpressure handling."""

import asyncio
import pytest

from streamweaver import BackpressurePolicy, BackpressureQueue


class TestBackpressureQueue:
    """Tests for BackpressureQueue class."""

    @pytest.mark.asyncio
    async def test_basic_put_get(self):
        """Test basic put and get operations."""
        queue = BackpressureQueue(maxsize=10)

        await queue.put("item1")
        await queue.put("item2")

        assert queue.qsize() == 2
        assert not queue.empty()
        assert not queue.full()

        item = await queue.get()
        assert item == "item1"
        assert queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_unlimited_queue(self):
        """Test queue with unlimited size."""
        queue = BackpressureQueue(maxsize=0)

        for i in range(100):
            await queue.put(f"item{i}")

        assert queue.qsize() == 100
        assert not queue.full()

    @pytest.mark.asyncio
    async def test_drop_oldest_policy(self):
        """Test DROP_OLDEST policy when queue is full."""
        queue = BackpressureQueue(maxsize=3, policy=BackpressurePolicy.DROP_OLDEST)

        # Fill the queue
        await queue.put("item1")
        await queue.put("item2")
        await queue.put("item3")

        assert queue.qsize() == 3
        assert queue.full()

        # Add one more - should drop oldest
        result = await queue.put("item4")

        assert result is True
        assert queue.qsize() == 3
        assert queue.dropped_count == 1

        # First item should be "item2" now
        item = await queue.get()
        assert item == "item2"

    @pytest.mark.asyncio
    async def test_drop_newest_policy(self):
        """Test DROP_NEWEST policy when queue is full."""
        queue = BackpressureQueue(maxsize=3, policy=BackpressurePolicy.DROP_NEWEST)

        # Fill the queue
        await queue.put("item1")
        await queue.put("item2")
        await queue.put("item3")

        # Add one more - should be dropped
        result = await queue.put("item4")

        assert result is False
        assert queue.qsize() == 3
        assert queue.dropped_count == 1

        # First item should still be "item1"
        item = await queue.get()
        assert item == "item1"

    @pytest.mark.asyncio
    async def test_get_with_timeout(self):
        """Test get with timeout."""
        queue = BackpressureQueue(maxsize=10)

        await queue.put("item")

        # Should succeed
        item = await queue.get(timeout=1.0)
        assert item == "item"

        # Should timeout
        with pytest.raises(asyncio.TimeoutError):
            await queue.get(timeout=0.1)

    @pytest.mark.asyncio
    async def test_get_nowait(self):
        """Test get_nowait."""
        queue = BackpressureQueue(maxsize=10)

        await queue.put("item")
        item = queue.get_nowait()
        assert item == "item"

        with pytest.raises(asyncio.QueueEmpty):
            queue.get_nowait()

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing the queue."""
        queue = BackpressureQueue(maxsize=10)

        for i in range(5):
            await queue.put(f"item{i}")

        cleared = await queue.clear()

        assert cleared == 5
        assert queue.qsize() == 0
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_reset_dropped_count(self):
        """Test resetting the dropped count."""
        queue = BackpressureQueue(maxsize=2, policy=BackpressurePolicy.DROP_OLDEST)

        await queue.put("item1")
        await queue.put("item2")
        await queue.put("item3")  # Drops item1
        await queue.put("item4")  # Drops item2

        assert queue.dropped_count == 2

        previous = queue.reset_dropped_count()

        assert previous == 2
        assert queue.dropped_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent put and get operations."""
        queue = BackpressureQueue(maxsize=100, policy=BackpressurePolicy.DROP_OLDEST)
        received = []

        async def producer():
            for i in range(50):
                await queue.put(i)
                await asyncio.sleep(0.001)

        async def consumer():
            for _ in range(50):
                try:
                    item = await queue.get(timeout=1.0)
                    received.append(item)
                except asyncio.TimeoutError:
                    break

        await asyncio.gather(producer(), consumer())

        assert len(received) == 50

    @pytest.mark.asyncio
    async def test_multiple_drops(self):
        """Test multiple consecutive drops."""
        queue = BackpressureQueue(maxsize=2, policy=BackpressurePolicy.DROP_OLDEST)

        await queue.put("item1")
        await queue.put("item2")

        # Add 5 more items - should drop 5 old items
        for i in range(5):
            await queue.put(f"new{i}")

        assert queue.dropped_count == 5
        assert queue.qsize() == 2

        # Last two items should be new3 and new4
        item1 = await queue.get()
        item2 = await queue.get()
        assert item1 == "new3"
        assert item2 == "new4"
