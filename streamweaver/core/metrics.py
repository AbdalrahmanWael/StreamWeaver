"""
Observability and metrics for StreamWeaver.

Provides Prometheus-compatible metrics for monitoring streaming performance.
Metrics are only active if prometheus_client is installed.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import prometheus_client, but don't fail if it's not installed
try:
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.debug("prometheus_client not installed - metrics disabled")


class NoOpMetric:
    """No-op metric for when prometheus is not available."""

    def inc(self, *args: Any, **kwargs: Any) -> None:
        pass

    def dec(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set(self, *args: Any, **kwargs: Any) -> None:
        pass

    def observe(self, *args: Any, **kwargs: Any) -> None:
        pass

    def labels(self, *args: Any, **kwargs: Any) -> "NoOpMetric":
        return self

    def info(self, *args: Any, **kwargs: Any) -> None:
        pass


class StreamWeaverMetrics:
    """
    Prometheus metrics for StreamWeaver.

    Provides counters, gauges, and histograms for monitoring:
    - Event publishing rate and latency
    - Session lifecycle
    - Stream connections
    - Queue depths
    - Error rates
    """

    def __init__(
        self,
        enabled: bool = True,
        prefix: str = "streamweaver",
        registry: Optional[Any] = None,
    ):
        """
        Initialize metrics.

        Args:
            enabled: Whether metrics collection is enabled.
            prefix: Prefix for all metric names.
            registry: Optional custom Prometheus registry.
        """
        self.enabled = enabled and PROMETHEUS_AVAILABLE
        self.prefix = prefix
        self._registry = registry

        if self.enabled:
            self._init_prometheus_metrics()
        else:
            self._init_noop_metrics()

    def _init_prometheus_metrics(self) -> None:
        """Initialize real Prometheus metrics."""
        reg = self._registry or REGISTRY

        # Event metrics
        self.events_published = Counter(
            f"{self.prefix}_events_published_total",
            "Total number of events published",
            ["session_id", "event_type"],
            registry=reg,
        )

        self.events_dropped = Counter(
            f"{self.prefix}_events_dropped_total",
            "Total number of events dropped due to backpressure",
            ["session_id", "reason"],
            registry=reg,
        )

        self.event_publish_duration = Histogram(
            f"{self.prefix}_event_publish_duration_seconds",
            "Time taken to publish an event",
            ["event_type"],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
            registry=reg,
        )

        # Session metrics
        self.sessions_created = Counter(
            f"{self.prefix}_sessions_created_total",
            "Total number of sessions created",
            registry=reg,
        )

        self.sessions_closed = Counter(
            f"{self.prefix}_sessions_closed_total",
            "Total number of sessions closed",
            ["reason"],
            registry=reg,
        )

        self.active_sessions = Gauge(
            f"{self.prefix}_active_sessions",
            "Number of currently active sessions",
            registry=reg,
        )

        # Stream metrics
        self.active_streams = Gauge(
            f"{self.prefix}_active_streams",
            "Number of currently active SSE streams",
            registry=reg,
        )

        self.stream_connections = Counter(
            f"{self.prefix}_stream_connections_total",
            "Total number of stream connections",
            ["reconnection"],
            registry=reg,
        )

        self.stream_disconnections = Counter(
            f"{self.prefix}_stream_disconnections_total",
            "Total number of stream disconnections",
            ["reason"],
            registry=reg,
        )

        # Queue metrics
        self.queue_depth = Gauge(
            f"{self.prefix}_queue_depth",
            "Current depth of event queues",
            ["session_id"],
            registry=reg,
        )

        self.queue_max_depth = Gauge(
            f"{self.prefix}_queue_max_depth_reached",
            "Maximum queue depth reached per session",
            ["session_id"],
            registry=reg,
        )

        # Replay metrics
        self.replay_requests = Counter(
            f"{self.prefix}_replay_requests_total",
            "Total number of replay requests",
            ["success"],
            registry=reg,
        )

        self.events_replayed = Counter(
            f"{self.prefix}_events_replayed_total",
            "Total number of events replayed",
            registry=reg,
        )

        # Error metrics
        self.errors = Counter(
            f"{self.prefix}_errors_total",
            "Total number of errors",
            ["error_type"],
            registry=reg,
        )

        logger.info("Prometheus metrics initialized")

    def _init_noop_metrics(self) -> None:
        """Initialize no-op metrics when Prometheus is not available."""
        noop = NoOpMetric()
        self.events_published = noop  # type: ignore[assignment]
        self.events_dropped = noop  # type: ignore[assignment]
        self.event_publish_duration = noop  # type: ignore[assignment]
        self.sessions_created = noop  # type: ignore[assignment]
        self.sessions_closed = noop  # type: ignore[assignment]
        self.active_sessions = noop  # type: ignore[assignment]
        self.active_streams = noop  # type: ignore[assignment]
        self.stream_connections = noop  # type: ignore[assignment]
        self.stream_disconnections = noop  # type: ignore[assignment]
        self.queue_depth = noop  # type: ignore[assignment]
        self.queue_max_depth = noop  # type: ignore[assignment]
        self.replay_requests = noop  # type: ignore[assignment]
        self.events_replayed = noop  # type: ignore[assignment]
        self.errors = noop  # type: ignore[assignment]

    @contextmanager
    def measure_publish_time(self, event_type: str):
        """Context manager to measure event publish duration."""
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.event_publish_duration.labels(event_type=event_type).observe(duration)

    def record_event_published(self, session_id: str, event_type: str) -> None:
        """Record that an event was published."""
        if self.enabled:
            self.events_published.labels(session_id=session_id, event_type=event_type).inc()

    def record_event_dropped(self, session_id: str, reason: str = "backpressure") -> None:
        """Record that an event was dropped."""
        if self.enabled:
            self.events_dropped.labels(session_id=session_id, reason=reason).inc()

    def record_session_created(self) -> None:
        """Record that a session was created."""
        if self.enabled:
            self.sessions_created.inc()
            self.active_sessions.inc()

    def record_session_closed(self, reason: str = "completed") -> None:
        """Record that a session was closed."""
        if self.enabled:
            self.sessions_closed.labels(reason=reason).inc()
            self.active_sessions.dec()

    def record_stream_connected(self, reconnection: bool = False) -> None:
        """Record a stream connection."""
        if self.enabled:
            self.active_streams.inc()
            self.stream_connections.labels(reconnection=str(reconnection).lower()).inc()

    def record_stream_disconnected(self, reason: str = "client_close") -> None:
        """Record a stream disconnection."""
        if self.enabled:
            self.active_streams.dec()
            self.stream_disconnections.labels(reason=reason).inc()

    def update_queue_depth(self, session_id: str, depth: int) -> None:
        """Update the current queue depth for a session."""
        if self.enabled:
            self.queue_depth.labels(session_id=session_id).set(depth)

    def record_replay(self, success: bool, event_count: int = 0) -> None:
        """Record a replay request."""
        if self.enabled:
            self.replay_requests.labels(success=str(success).lower()).inc()
            if success and event_count > 0:
                self.events_replayed.inc(event_count)

    def record_error(self, error_type: str) -> None:
        """Record an error."""
        if self.enabled:
            self.errors.labels(error_type=error_type).inc()


# Global metrics instance (can be replaced with custom instance)
_global_metrics: Optional[StreamWeaverMetrics] = None


def get_metrics() -> StreamWeaverMetrics:
    """Get the global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = StreamWeaverMetrics(enabled=False)
    return _global_metrics


def init_metrics(
    enabled: bool = True,
    prefix: str = "streamweaver",
    registry: Optional[Any] = None,
) -> StreamWeaverMetrics:
    """
    Initialize the global metrics instance.

    Args:
        enabled: Whether to enable metrics collection.
        prefix: Prefix for metric names.
        registry: Optional custom Prometheus registry.

    Returns:
        The initialized metrics instance.
    """
    global _global_metrics
    _global_metrics = StreamWeaverMetrics(enabled=enabled, prefix=prefix, registry=registry)
    return _global_metrics
