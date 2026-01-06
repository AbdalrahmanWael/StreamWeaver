"""Tests for StreamEvent and event types."""

import pytest
import time
import json

from streamweaver import (
    StreamEvent,
    StreamEventType,
    EventVisibility,
    generate_event_id,
)


class TestStreamEventType:
    """Tests for StreamEventType enum."""

    def test_all_event_types_exist(self):
        """Test that all expected event types are defined."""
        expected_types = [
            "WORKFLOW_STARTED",
            "WORKFLOW_COMPLETED",
            "STEP_STARTED",
            "STEP_PROGRESS",
            "STEP_COMPLETED",
            "STEP_FAILED",
            "TOOL_EXECUTED",
            "TOOL_COMPLETED",
            "ERROR",
            "HEARTBEAT",
            "AGENT_MESSAGE",
            "TOKEN_CHUNK",
            "WORKFLOW_INTERRUPTION",
            "REASONING_CHUNK",
            "USER_DECISION",
        ]
        
        for type_name in expected_types:
            assert hasattr(StreamEventType, type_name)


class TestEventVisibility:
    """Tests for EventVisibility enum."""

    def test_all_visibility_levels_exist(self):
        """Test that all expected visibility levels are defined."""
        assert EventVisibility.USER_FACING.value == "user_facing"
        assert EventVisibility.MODEL_ONLY.value == "model_only"
        assert EventVisibility.LIVE_UI_ONLY.value == "live_ui_only"
        assert EventVisibility.INTERNAL_ONLY.value == "internal_only"


class TestGenerateEventId:
    """Tests for event ID generation."""

    def test_generates_unique_ids(self):
        """Test that each call generates a unique ID."""
        ids = [generate_event_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generates_valid_uuid(self):
        """Test that generated IDs are valid UUIDs."""
        event_id = generate_event_id()
        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        parts = event_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""

    def test_create_basic_event(self):
        """Test creating a basic event."""
        event = StreamEvent(
            event_type=StreamEventType.WORKFLOW_STARTED,
            session_id="test-session",
            timestamp=time.time(),
            message="Starting workflow",
        )
        
        assert event.event_type == StreamEventType.WORKFLOW_STARTED
        assert event.session_id == "test-session"
        assert event.message == "Starting workflow"
        assert event.success is True
        assert event.visibility == EventVisibility.USER_FACING

    def test_auto_generated_event_id(self):
        """Test that event ID is auto-generated."""
        event = StreamEvent(
            event_type=StreamEventType.STEP_PROGRESS,
            session_id="test",
            timestamp=time.time(),
        )
        
        assert event.event_id is not None
        assert len(event.event_id) > 0

    def test_custom_event_id(self):
        """Test using a custom event ID."""
        custom_id = "custom-event-123"
        event = StreamEvent(
            event_type=StreamEventType.STEP_PROGRESS,
            session_id="test",
            timestamp=time.time(),
            event_id=custom_id,
        )
        
        assert event.event_id == custom_id

    def test_event_with_data(self):
        """Test event with additional data."""
        data = {"key": "value", "count": 42}
        event = StreamEvent(
            event_type=StreamEventType.TOOL_EXECUTED,
            session_id="test",
            timestamp=time.time(),
            data=data,
            tool_used="search",
        )
        
        assert event.data == data
        assert event.tool_used == "search"

    def test_event_with_all_fields(self):
        """Test event with all optional fields."""
        metadata = {"source": "test"}
        event = StreamEvent(
            event_type=StreamEventType.STEP_PROGRESS,
            session_id="test",
            timestamp=1234567890.0,
            step_number=3,
            message="Processing...",
            data={"items": 10},
            progress_percent=75.5,
            tool_used="processor",
            duration_ms=1500,
            success=True,
            metadata=metadata,
            visibility=EventVisibility.LIVE_UI_ONLY,
        )
        
        assert event.step_number == 3
        assert event.progress_percent == 75.5
        assert event.duration_ms == 1500
        assert event.metadata == metadata
        assert event.visibility == EventVisibility.LIVE_UI_ONLY

    def test_to_sse_format(self):
        """Test conversion to SSE format."""
        event = StreamEvent(
            event_type=StreamEventType.STEP_PROGRESS,
            session_id="test-session",
            timestamp=1234567890.0,
            message="Processing",
        )
        
        sse = event.to_sse_format()
        
        # Check SSE structure
        assert f"id: {event.event_id}" in sse
        assert "event: message" in sse
        assert "data: " in sse
        assert sse.endswith("\n\n")
        
        # Parse and verify JSON data
        data_line = [line for line in sse.split("\n") if line.startswith("data: ")][0]
        json_data = json.loads(data_line[6:])
        
        assert json_data["type"] == "step_progress"
        assert json_data["sessionId"] == "test-session"
        assert json_data["message"] == "Processing"
        assert json_data["eventId"] == event.event_id

    def test_to_sse_format_excludes_none_values(self):
        """Test that SSE format excludes None values."""
        event = StreamEvent(
            event_type=StreamEventType.HEARTBEAT,
            session_id="test",
            timestamp=time.time(),
        )
        
        sse = event.to_sse_format()
        data_line = [line for line in sse.split("\n") if line.startswith("data: ")][0]
        json_data = json.loads(data_line[6:])
        
        # step should not be present since step_number was None
        assert "step" not in json_data

    def test_to_dict(self):
        """Test conversion to dictionary."""
        event = StreamEvent(
            event_type=StreamEventType.WORKFLOW_COMPLETED,
            session_id="test",
            timestamp=1234567890.0,
            message="Done",
            data={"result": "success"},
        )
        
        d = event.to_dict()
        
        assert d["type"] == "workflow_completed"
        assert d["sessionId"] == "test"
        assert d["message"] == "Done"
        assert d["data"] == {"result": "success"}
        assert d["eventId"] == event.event_id

    def test_from_dict(self):
        """Test creating event from dictionary."""
        data = {
            "type": "step_progress",
            "eventId": "custom-id",
            "sessionId": "test",
            "timestamp": 1234567890.0,
            "message": "Processing",
            "step": 2,
            "progress": 50.0,
            "visibility": "user_facing",
        }
        
        event = StreamEvent.from_dict(data)
        
        assert event.event_type == StreamEventType.STEP_PROGRESS
        assert event.event_id == "custom-id"
        assert event.session_id == "test"
        assert event.message == "Processing"
        assert event.step_number == 2
        assert event.progress_percent == 50.0
        assert event.visibility == EventVisibility.USER_FACING

    def test_from_dict_unknown_type(self):
        """Test creating event from dict with unknown event type."""
        data = {
            "type": "custom_type",
            "sessionId": "test",
            "timestamp": time.time(),
        }
        
        event = StreamEvent.from_dict(data)
        
        # Should keep as string
        assert event.event_type == "custom_type"

    def test_string_event_type(self):
        """Test event with string event type."""
        event = StreamEvent(
            event_type="custom_type",
            session_id="test",
            timestamp=time.time(),
        )
        
        sse = event.to_sse_format()
        assert "custom_type" in sse
