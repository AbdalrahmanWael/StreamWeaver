"""
Backpressure handling for StreamWeaver event queues.
"""

import asyncio
import contextlib
import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BackpressurePolicy(Enum):
    """Policy for handling queue overflow."""

    BLOCK = "block"  # Block until space is available (default asyncio.Queue behavior)
    DROP_OLDEST = "drop_oldest"  # Drop oldest events when full
    DROP_NEWEST = "drop_newest"  # Drop new events when full


class BackpressureQueue:
    """
    Async queue with configurable backpressure handling.

    Unlike asyncio.Queue, this queue can handle overflow gracefully
    using different policies instead of blocking indefinitely.
    """

    def __init__(
        self,
        maxsize: int = 1000,
        policy: BackpressurePolicy = BackpressurePolicy.DROP_OLDEST,
    ):
        """
        Initialize the backpressure queue.

        Args:
            maxsize: Maximum number of items in the queue. 0 means unlimited.
            policy: How to handle overflow when queue is full.
        """
        self.maxsize = maxsize
        self.policy = policy
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=0)  # Unbounded internal queue
        self._items: list = []  # For DROP_OLDEST we need direct access
        self._lock = asyncio.Lock()
        self._dropped_count = 0

    @property
    def dropped_count(self) -> int:
        """Number of events dropped due to backpressure."""
        return self._dropped_count

    def qsize(self) -> int:
        """Return the number of items in the queue."""
        return len(self._items)

    def empty(self) -> bool:
        """Return True if the queue is empty."""
        return len(self._items) == 0

    def full(self) -> bool:
        """Return True if the queue is full."""
        if self.maxsize <= 0:
            return False
        return len(self._items) >= self.maxsize

    async def put(self, item: Any) -> bool:
        """
        Put an item into the queue with backpressure handling.

        Args:
            item: The item to put into the queue.

        Returns:
            True if the item was added, False if it was dropped.
        """
        async with self._lock:
            if self.maxsize <= 0:
                # Unlimited queue
                self._items.append(item)
                await self._queue.put(item)
                return True

            if len(self._items) < self.maxsize:
                # Queue has space
                self._items.append(item)
                await self._queue.put(item)
                return True

            # Queue is full, apply policy
            if self.policy == BackpressurePolicy.BLOCK:
                # Release lock and wait for space
                pass  # Fall through to blocking put
            elif self.policy == BackpressurePolicy.DROP_OLDEST:
                # Remove oldest item
                if self._items:
                    self._items.pop(0)
                    with contextlib.suppress(asyncio.QueueEmpty):
                        self._queue.get_nowait()
                    self._dropped_count += 1
                    logger.debug(f"Dropped oldest event (total dropped: {self._dropped_count})")
                self._items.append(item)
                await self._queue.put(item)
                return True
            elif self.policy == BackpressurePolicy.DROP_NEWEST:
                # Drop the new item
                self._dropped_count += 1
                logger.debug(f"Dropped newest event (total dropped: {self._dropped_count})")
                return False

        # BLOCK policy - wait for space
        # This is outside the lock to allow concurrent gets
        self._items.append(item)
        await self._queue.put(item)
        return True

    async def get(self, timeout: Optional[float] = None) -> Any:
        """
        Get an item from the queue.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            The next item from the queue.

        Raises:
            asyncio.TimeoutError: If timeout expires.
        """
        if timeout is not None:
            item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        else:
            item = await self._queue.get()

        async with self._lock:
            if item in self._items:
                self._items.remove(item)

        return item

    def get_nowait(self) -> Any:
        """Get an item without waiting."""
        item = self._queue.get_nowait()
        if item in self._items:
            self._items.remove(item)
        return item

    async def clear(self) -> int:
        """
        Clear all items from the queue.

        Returns:
            Number of items cleared.
        """
        async with self._lock:
            count = len(self._items)
            self._items.clear()
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            return count

    def reset_dropped_count(self) -> int:
        """Reset the dropped count and return the previous value."""
        count = self._dropped_count
        self._dropped_count = 0
        return count
