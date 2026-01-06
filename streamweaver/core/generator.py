"""
Stream generator for SSE events.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional

from .backpressure import BackpressurePolicy, BackpressureQueue
from .events import EventVisibility, StreamEvent, StreamEventType
from .filters import EventFilter
from .replay import SessionEventBuffers

logger = logging.getLogger(__name__)


class StreamGenerator:
    """
    High-performance SSE stream generator with replay, backpressure, and filtering support.
    """

    def __init__(
        self,
        session_store: Any,
        queue_size: int = 1000,
        backpressure_policy: BackpressurePolicy = BackpressurePolicy.DROP_OLDEST,
        heartbeat_interval: int = 30,
        event_buffer_size: int = 100,
    ):
        """
        Initialize the stream generator.
        
        Args:
            session_store: Session storage backend.
            queue_size: Maximum size of event queues.
            backpressure_policy: Policy for handling queue overflow.
            heartbeat_interval: Seconds between heartbeat events.
            event_buffer_size: Max events to buffer per session for replay.
        """
        self.session_store = session_store
        self.queue_size = queue_size
        self.backpressure_policy = backpressure_policy
        self.heartbeat_interval = heartbeat_interval
        self.event_buffer_size = event_buffer_size

        self.active_streams: Dict[str, BackpressureQueue] = {}
        self.active_stream_tasks: Dict[str, asyncio.Task] = {}
        self._event_callbacks: Dict[str, Callable[[StreamEvent], Awaitable[None]]] = {}
        self._event_buffers = SessionEventBuffers(buffer_size=event_buffer_size)

    def register_event_callback(
        self,
        session_id: str,
        callback: Optional[Callable[[StreamEvent], Awaitable[None]]],
    ) -> None:
        """Register or clear a callback for a specific session_id."""
        if callback:
            self._event_callbacks[session_id] = callback
            logger.debug(f"Registered event callback for session: {session_id}")
        else:
            if session_id in self._event_callbacks:
                del self._event_callbacks[session_id]
                logger.debug(f"Unregistered event callback for session: {session_id}")

    async def publish_event(self, session_id: str, event: StreamEvent) -> bool:
        """
        Publish an event to a specific session stream.
        
        Args:
            session_id: Target session.
            event: The event to publish.
            
        Returns:
            True if event was queued, False if dropped due to backpressure.
        """
        # Store in replay buffer
        await self._event_buffers.add_event(session_id, event)

        # Call registered callback
        callback = self._event_callbacks.get(session_id)
        if callback:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

        # Ensure queue exists
        if session_id not in self.active_streams:
            logger.debug(f"Pre-creating event queue for session {session_id}")
            self.active_streams[session_id] = BackpressureQueue(
                maxsize=self.queue_size,
                policy=self.backpressure_policy,
            )

        queue = self.active_streams[session_id]
        try:
            success = await queue.put(event)
            if success:
                await self.session_store.update_session(
                    session_id,
                    last_activity=event.timestamp,
                    current_step=event.message,
                )
            else:
                logger.warning(f"Event dropped for session {session_id} due to backpressure")
            return success
        except Exception as e:
            logger.error(f"Failed to publish event to session {session_id}: {e}")
            return False

    async def generate_stream(
        self,
        session_id: str,
        last_event_id: Optional[str] = None,
        event_filter: Optional[EventFilter] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Generate SSE stream for a specific session.
        
        Args:
            session_id: The session to stream.
            last_event_id: Optional Last-Event-ID for replay.
            event_filter: Optional filter to apply to events.
            
        Yields:
            SSE-formatted event strings.
        """
        # Handle reconnection with replay
        if last_event_id:
            replay_events = await self._event_buffers.get_events_after(
                session_id, last_event_id
            )
            for event in replay_events:
                if event_filter and not event_filter.should_include(event):
                    continue
                yield event.to_sse_format()
            logger.info(f"Replayed {len(replay_events)} events for session {session_id}")

        # Get or create queue
        existing_queue = self.active_streams.get(session_id)
        if existing_queue:
            logger.debug(f"Using existing queue for {session_id}")
            event_queue = existing_queue
        else:
            logger.debug(f"Creating new queue for {session_id}")
            event_queue = BackpressureQueue(
                maxsize=self.queue_size,
                policy=self.backpressure_policy,
            )
            self.active_streams[session_id] = event_queue

        current_task = asyncio.current_task()
        if current_task:
            self.active_stream_tasks[session_id] = current_task

        heartbeat_task = None

        try:
            # Send initial connection event (only if not reconnecting)
            if not last_event_id:
                initial_event = StreamEvent(
                    event_type=StreamEventType.WORKFLOW_STARTED,
                    session_id=session_id,
                    timestamp=asyncio.get_event_loop().time(),
                    message="Connected to stream",
                    visibility=EventVisibility.USER_FACING,
                )
                if not event_filter or event_filter.should_include(initial_event):
                    yield initial_event.to_sse_format()
                logger.info(f"Stream started for session {session_id}")

            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._heartbeat_generator(session_id, event_queue)
            )

            while True:
                try:
                    event = await event_queue.get(timeout=15.0)

                    # Apply filter
                    if event_filter and not event_filter.should_include(event):
                        continue

                    if event.event_type == StreamEventType.WORKFLOW_COMPLETED:
                        logger.info(f"Workflow completed for session {session_id}")
                        yield event.to_sse_format()
                        break

                    yield event.to_sse_format()

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error in stream processing for {session_id}: {e}")
                    error_event = StreamEvent(
                        event_type=StreamEventType.ERROR,
                        session_id=session_id,
                        timestamp=asyncio.get_event_loop().time(),
                        message=f"Stream error: {str(e)}",
                        success=False,
                    )
                    yield error_event.to_sse_format()

        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")
            raise
        except Exception as e:
            logger.error(f"Fatal stream error for {session_id}: {e}")
            error_event = StreamEvent(
                event_type=StreamEventType.ERROR,
                session_id=session_id,
                timestamp=asyncio.get_event_loop().time(),
                message=f"Fatal stream error: {str(e)}",
                success=False,
            )
            yield error_event.to_sse_format()
        finally:
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

            if (
                session_id in self.active_streams
                and self.active_streams[session_id] is event_queue
            ):
                self.active_streams.pop(session_id, None)

            if session_id in self.active_stream_tasks:
                del self.active_stream_tasks[session_id]

            logger.debug(f"Stream closed for session: {session_id}")

    async def _heartbeat_generator(
        self,
        session_id: str,
        event_queue: BackpressureQueue,
    ) -> None:
        """Generate periodic heartbeat events."""
        heartbeat_sequence = 0
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                # Skip heartbeat if queue is backing up
                if event_queue.qsize() > 5:
                    continue

                heartbeat_sequence += 1
                heartbeat = StreamEvent(
                    event_type=StreamEventType.HEARTBEAT,
                    session_id=session_id,
                    timestamp=asyncio.get_event_loop().time(),
                    message="Heartbeat",
                    data={"sequence": heartbeat_sequence},
                    visibility=EventVisibility.INTERNAL_ONLY,
                )

                await event_queue.put(heartbeat)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error for session {session_id}: {e}")

    async def cancel_stream(self, session_id: str) -> None:
        """Cancel an active stream for a session."""
        if session_id in self.active_stream_tasks:
            task = self.active_stream_tasks[session_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.active_stream_tasks[session_id]

    async def cleanup_queue(self, session_id: str) -> None:
        """Clean up event queue for a session."""
        queue = self.active_streams.pop(session_id, None)
        if queue is not None:
            try:
                stale_event = StreamEvent(
                    event_type=StreamEventType.WORKFLOW_INTERRUPTION,
                    session_id=session_id,
                    timestamp=asyncio.get_event_loop().time(),
                    message="Stream has been superseded by a new connection",
                    success=False,
                )
                await queue.put(stale_event)
            except Exception:
                pass

        # Clear replay buffer
        await self._event_buffers.clear_session(session_id)

    def ensure_queue(self, session_id: str) -> None:
        """Pre-create the event queue for a session."""
        if session_id not in self.active_streams:
            self.active_streams[session_id] = BackpressureQueue(
                maxsize=self.queue_size,
                policy=self.backpressure_policy,
            )
            logger.debug(f"Pre-created event queue for session {session_id}")

    async def get_replay_events(
        self,
        session_id: str,
        last_event_id: str,
    ) -> List[StreamEvent]:
        """Get events for replay after the given event ID."""
        return await self._event_buffers.get_events_after(session_id, last_event_id)

    def get_queue_stats(self, session_id: str) -> Dict[str, Any]:
        """Get queue statistics for a session."""
        queue = self.active_streams.get(session_id)
        if queue is None:
            return {
                "exists": False,
                "size": 0,
                "max_size": self.queue_size,
                "dropped": 0,
            }
        return {
            "exists": True,
            "size": queue.qsize(),
            "max_size": self.queue_size,
            "dropped": queue.dropped_count,
            "full": queue.full(),
        }
