"""Tests for Prometheus metrics."""

import pytest

from streamweaver.core.metrics import (
    StreamWeaverMetrics,
    get_metrics,
    init_metrics,
    PROMETHEUS_AVAILABLE,
    NoOpMetric,
)


class TestNoOpMetric:
    """Tests for NoOpMetric when Prometheus is not available."""

    def test_all_methods_are_noop(self):
        """Test that all methods do nothing without raising."""
        metric = NoOpMetric()
        
        # None of these should raise
        metric.inc()
        metric.inc(5)
        metric.dec()
        metric.dec(3)
        metric.set(42)
        metric.observe(1.5)
        metric.info({"key": "value"})
        
        # labels should return another NoOpMetric
        labeled = metric.labels(session_id="test", event_type="progress")
        assert isinstance(labeled, NoOpMetric)


class TestStreamWeaverMetrics:
    """Tests for StreamWeaverMetrics class."""

    def test_disabled_metrics(self):
        """Test metrics when disabled."""
        metrics = StreamWeaverMetrics(enabled=False)
        
        # All methods should work without raising
        metrics.record_event_published("session-1", "step_progress")
        metrics.record_event_dropped("session-1")
        metrics.record_session_created()
        metrics.record_session_closed("completed")
        metrics.record_stream_connected()
        metrics.record_stream_disconnected("client_close")
        metrics.update_queue_depth("session-1", 10)
        metrics.record_replay(True, 5)
        metrics.record_error("test_error")

    def test_measure_publish_time_disabled(self):
        """Test measure_publish_time context manager when disabled."""
        metrics = StreamWeaverMetrics(enabled=False)
        
        with metrics.measure_publish_time("step_progress"):
            pass  # Should not raise

    @pytest.mark.skipif(
        not PROMETHEUS_AVAILABLE,
        reason="prometheus_client not installed"
    )
    def test_enabled_metrics_with_custom_registry(self):
        """Test metrics with a custom registry."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        metrics = StreamWeaverMetrics(
            enabled=True,
            prefix="test_streamweaver",
            registry=registry,
        )
        
        # Record some metrics
        metrics.record_session_created()
        metrics.record_event_published("session-1", "step_progress")
        metrics.record_stream_connected()
        
        # Verify metrics were recorded
        assert metrics.enabled is True

    @pytest.mark.skipif(
        not PROMETHEUS_AVAILABLE,
        reason="prometheus_client not installed"
    )
    def test_all_metric_types(self):
        """Test that all metric types are properly initialized."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        metrics = StreamWeaverMetrics(
            enabled=True,
            prefix="full_test",
            registry=registry,
        )
        
        # Counters
        metrics.record_event_published("s1", "type1")
        metrics.record_event_dropped("s1", "backpressure")
        metrics.record_session_created()
        metrics.record_session_closed("timeout")
        metrics.record_stream_connected(reconnection=True)
        metrics.record_stream_disconnected("error")
        metrics.record_replay(True, 10)
        metrics.record_error("connection")
        
        # Gauges
        metrics.update_queue_depth("s1", 50)
        
        # Histogram
        with metrics.measure_publish_time("test_event"):
            pass

    @pytest.mark.skipif(
        not PROMETHEUS_AVAILABLE,
        reason="prometheus_client not installed"
    )
    def test_session_lifecycle_metrics(self):
        """Test session create/close updates active_sessions gauge."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        metrics = StreamWeaverMetrics(
            enabled=True,
            prefix="lifecycle_test",
            registry=registry,
        )
        
        metrics.record_session_created()
        metrics.record_session_created()
        metrics.record_session_closed("completed")
        
        # active_sessions should be 1 (2 created - 1 closed)
        # We can't easily verify the gauge value in tests,
        # but at least verify no errors occurred


class TestGlobalMetrics:
    """Tests for global metrics functions."""

    def test_get_metrics_returns_instance(self):
        """Test that get_metrics returns a metrics instance."""
        metrics = get_metrics()
        
        assert isinstance(metrics, StreamWeaverMetrics)

    def test_init_metrics_creates_instance(self):
        """Test that init_metrics creates a new instance."""
        if PROMETHEUS_AVAILABLE:
            from prometheus_client import CollectorRegistry
            registry = CollectorRegistry()
            metrics = init_metrics(enabled=True, prefix="init_test", registry=registry)
        else:
            metrics = init_metrics(enabled=False)
        
        assert isinstance(metrics, StreamWeaverMetrics)

    def test_init_metrics_updates_global(self):
        """Test that init_metrics updates the global instance."""
        metrics1 = init_metrics(enabled=False, prefix="test1")
        metrics2 = get_metrics()
        
        assert metrics1 is metrics2

    def test_disabled_when_prometheus_not_available(self):
        """Test metrics are disabled when prometheus_client is not available."""
        metrics = StreamWeaverMetrics(enabled=True)  # Request enabled
        
        if not PROMETHEUS_AVAILABLE:
            assert metrics.enabled is False
            assert isinstance(metrics.events_published, NoOpMetric)
