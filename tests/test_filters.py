"""Tests for event filtering."""

import pytest
import time

from streamweaver import (
    StreamEvent,
    StreamEventType,
    EventVisibility,
    EventFilter,
    VisibilityFilter,
    TypeFilter,
    CompositeFilter,
    NotFilter,
    CallableFilter,
    SessionFilter,
    apply_filter,
    USER_FACING_FILTER,
    LIVE_UI_FILTER,
    NO_HEARTBEAT_FILTER,
    PROGRESS_ONLY_FILTER,
)


def create_event(
    event_type=StreamEventType.STEP_PROGRESS,
    visibility=EventVisibility.USER_FACING,
    session_id="test-session",
) -> StreamEvent:
    """Helper to create test events."""
    return StreamEvent(
        event_type=event_type,
        session_id=session_id,
        timestamp=time.time(),
        visibility=visibility,
    )


class TestVisibilityFilter:
    """Tests for VisibilityFilter."""

    def test_single_visibility(self):
        """Test filter with single visibility."""
        filter_ = VisibilityFilter(EventVisibility.USER_FACING)
        
        user_event = create_event(visibility=EventVisibility.USER_FACING)
        internal_event = create_event(visibility=EventVisibility.INTERNAL_ONLY)
        
        assert filter_.should_include(user_event) is True
        assert filter_.should_include(internal_event) is False

    def test_multiple_visibilities(self):
        """Test filter with multiple visibilities."""
        filter_ = VisibilityFilter([
            EventVisibility.USER_FACING,
            EventVisibility.LIVE_UI_ONLY,
        ])
        
        user_event = create_event(visibility=EventVisibility.USER_FACING)
        live_ui_event = create_event(visibility=EventVisibility.LIVE_UI_ONLY)
        internal_event = create_event(visibility=EventVisibility.INTERNAL_ONLY)
        
        assert filter_.should_include(user_event) is True
        assert filter_.should_include(live_ui_event) is True
        assert filter_.should_include(internal_event) is False


class TestTypeFilter:
    """Tests for TypeFilter."""

    def test_include_type(self):
        """Test including specific event types."""
        filter_ = TypeFilter(StreamEventType.WORKFLOW_STARTED, include=True)
        
        started_event = create_event(event_type=StreamEventType.WORKFLOW_STARTED)
        progress_event = create_event(event_type=StreamEventType.STEP_PROGRESS)
        
        assert filter_.should_include(started_event) is True
        assert filter_.should_include(progress_event) is False

    def test_exclude_type(self):
        """Test excluding specific event types."""
        filter_ = TypeFilter(StreamEventType.HEARTBEAT, include=False)
        
        heartbeat = create_event(event_type=StreamEventType.HEARTBEAT)
        progress = create_event(event_type=StreamEventType.STEP_PROGRESS)
        
        assert filter_.should_include(heartbeat) is False
        assert filter_.should_include(progress) is True

    def test_multiple_types(self):
        """Test filter with multiple event types."""
        filter_ = TypeFilter([
            StreamEventType.WORKFLOW_STARTED,
            StreamEventType.WORKFLOW_COMPLETED,
        ])
        
        started = create_event(event_type=StreamEventType.WORKFLOW_STARTED)
        completed = create_event(event_type=StreamEventType.WORKFLOW_COMPLETED)
        progress = create_event(event_type=StreamEventType.STEP_PROGRESS)
        
        assert filter_.should_include(started) is True
        assert filter_.should_include(completed) is True
        assert filter_.should_include(progress) is False

    def test_string_type(self):
        """Test filter with string event type."""
        filter_ = TypeFilter("workflow_started")
        
        started = create_event(event_type=StreamEventType.WORKFLOW_STARTED)
        
        assert filter_.should_include(started) is True


class TestCompositeFilter:
    """Tests for CompositeFilter."""

    def test_and_operator(self):
        """Test combining filters with AND."""
        visibility_filter = VisibilityFilter(EventVisibility.USER_FACING)
        type_filter = TypeFilter(StreamEventType.STEP_PROGRESS)
        
        composite = CompositeFilter([visibility_filter, type_filter], operator="and")
        
        # Both conditions met
        good_event = create_event(
            event_type=StreamEventType.STEP_PROGRESS,
            visibility=EventVisibility.USER_FACING,
        )
        assert composite.should_include(good_event) is True
        
        # Only visibility matches
        bad_event1 = create_event(
            event_type=StreamEventType.HEARTBEAT,
            visibility=EventVisibility.USER_FACING,
        )
        assert composite.should_include(bad_event1) is False
        
        # Only type matches
        bad_event2 = create_event(
            event_type=StreamEventType.STEP_PROGRESS,
            visibility=EventVisibility.INTERNAL_ONLY,
        )
        assert composite.should_include(bad_event2) is False

    def test_or_operator(self):
        """Test combining filters with OR."""
        type_filter1 = TypeFilter(StreamEventType.WORKFLOW_STARTED)
        type_filter2 = TypeFilter(StreamEventType.WORKFLOW_COMPLETED)
        
        composite = CompositeFilter([type_filter1, type_filter2], operator="or")
        
        started = create_event(event_type=StreamEventType.WORKFLOW_STARTED)
        completed = create_event(event_type=StreamEventType.WORKFLOW_COMPLETED)
        progress = create_event(event_type=StreamEventType.STEP_PROGRESS)
        
        assert composite.should_include(started) is True
        assert composite.should_include(completed) is True
        assert composite.should_include(progress) is False

    def test_operator_shorthand(self):
        """Test & and | operators."""
        filter1 = VisibilityFilter(EventVisibility.USER_FACING)
        filter2 = TypeFilter(StreamEventType.STEP_PROGRESS)
        
        and_filter = filter1 & filter2
        assert isinstance(and_filter, CompositeFilter)
        
        or_filter = filter1 | filter2
        assert isinstance(or_filter, CompositeFilter)


class TestNotFilter:
    """Tests for NotFilter."""

    def test_invert_filter(self):
        """Test inverting a filter."""
        base_filter = TypeFilter(StreamEventType.HEARTBEAT)
        not_filter = NotFilter(base_filter)
        
        heartbeat = create_event(event_type=StreamEventType.HEARTBEAT)
        progress = create_event(event_type=StreamEventType.STEP_PROGRESS)
        
        assert not_filter.should_include(heartbeat) is False
        assert not_filter.should_include(progress) is True

    def test_invert_shorthand(self):
        """Test ~ operator."""
        base_filter = TypeFilter(StreamEventType.HEARTBEAT)
        not_filter = ~base_filter
        
        assert isinstance(not_filter, NotFilter)


class TestCallableFilter:
    """Tests for CallableFilter."""

    def test_custom_predicate(self):
        """Test filter with custom predicate."""
        def has_data(event: StreamEvent) -> bool:
            return event.data is not None
        
        filter_ = CallableFilter(has_data)
        
        with_data = StreamEvent(
            event_type=StreamEventType.STEP_PROGRESS,
            session_id="test",
            timestamp=time.time(),
            data={"key": "value"},
        )
        without_data = create_event()
        
        assert filter_.should_include(with_data) is True
        assert filter_.should_include(without_data) is False


class TestSessionFilter:
    """Tests for SessionFilter."""

    def test_include_sessions(self):
        """Test including specific sessions."""
        filter_ = SessionFilter(["session-1", "session-2"])
        
        event1 = create_event(session_id="session-1")
        event2 = create_event(session_id="session-2")
        event3 = create_event(session_id="session-3")
        
        assert filter_.should_include(event1) is True
        assert filter_.should_include(event2) is True
        assert filter_.should_include(event3) is False

    def test_exclude_sessions(self):
        """Test excluding specific sessions."""
        filter_ = SessionFilter(["blocked-session"], include=False)
        
        blocked = create_event(session_id="blocked-session")
        allowed = create_event(session_id="allowed-session")
        
        assert filter_.should_include(blocked) is False
        assert filter_.should_include(allowed) is True


class TestPrebuiltFilters:
    """Tests for pre-built filter instances."""

    def test_user_facing_filter(self):
        """Test USER_FACING_FILTER."""
        user = create_event(visibility=EventVisibility.USER_FACING)
        internal = create_event(visibility=EventVisibility.INTERNAL_ONLY)
        
        assert USER_FACING_FILTER.should_include(user) is True
        assert USER_FACING_FILTER.should_include(internal) is False

    def test_live_ui_filter(self):
        """Test LIVE_UI_FILTER."""
        user = create_event(visibility=EventVisibility.USER_FACING)
        live_ui = create_event(visibility=EventVisibility.LIVE_UI_ONLY)
        internal = create_event(visibility=EventVisibility.INTERNAL_ONLY)
        
        assert LIVE_UI_FILTER.should_include(user) is True
        assert LIVE_UI_FILTER.should_include(live_ui) is True
        assert LIVE_UI_FILTER.should_include(internal) is False

    def test_no_heartbeat_filter(self):
        """Test NO_HEARTBEAT_FILTER."""
        heartbeat = create_event(event_type=StreamEventType.HEARTBEAT)
        progress = create_event(event_type=StreamEventType.STEP_PROGRESS)
        
        assert NO_HEARTBEAT_FILTER.should_include(heartbeat) is False
        assert NO_HEARTBEAT_FILTER.should_include(progress) is True

    def test_progress_only_filter(self):
        """Test PROGRESS_ONLY_FILTER."""
        started = create_event(event_type=StreamEventType.WORKFLOW_STARTED)
        progress = create_event(event_type=StreamEventType.STEP_PROGRESS)
        heartbeat = create_event(event_type=StreamEventType.HEARTBEAT)
        
        assert PROGRESS_ONLY_FILTER.should_include(started) is True
        assert PROGRESS_ONLY_FILTER.should_include(progress) is True
        assert PROGRESS_ONLY_FILTER.should_include(heartbeat) is False


class TestApplyFilter:
    """Tests for apply_filter helper function."""

    def test_apply_filter_to_list(self):
        """Test applying filter to a list of events."""
        events = [
            create_event(event_type=StreamEventType.WORKFLOW_STARTED),
            create_event(event_type=StreamEventType.HEARTBEAT),
            create_event(event_type=StreamEventType.STEP_PROGRESS),
            create_event(event_type=StreamEventType.HEARTBEAT),
            create_event(event_type=StreamEventType.WORKFLOW_COMPLETED),
        ]
        
        filtered = apply_filter(events, NO_HEARTBEAT_FILTER)
        
        assert len(filtered) == 3
        for event in filtered:
            assert event.event_type != StreamEventType.HEARTBEAT

    def test_apply_none_filter(self):
        """Test apply_filter with None filter returns all events."""
        events = [create_event() for _ in range(3)]
        
        result = apply_filter(events, None)
        
        assert len(result) == 3
        assert result == events
