"""
Core streaming event types and data models for StreamWeaver.
"""

import contextlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union


class EventVisibility(Enum):
    """Defines the audience and purpose of a given stream event."""

    USER_FACING = "user_facing"  # For user's chat UI AND model's conversation history.
    MODEL_ONLY = "model_only"  # For model's persistent memory, NOT for user chat UI.
    LIVE_UI_ONLY = "live_ui_only"  # For the real-time UI stream ONLY (e.g., reasoning tokens).
    INTERNAL_ONLY = "internal_only"  # For server logs/debugging. Not for UI or model.


class StreamEventType(Enum):
    """Types of streaming events in the agentic workflow"""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    STEP_STARTED = "step_started"
    STEP_PROGRESS = "step_progress"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    TOOL_EXECUTED = "tool_executed"
    TOOL_COMPLETED = "tool_completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    AGENT_MESSAGE = "agent_message"
    TOKEN_CHUNK = "token_chunk"
    WORKFLOW_INTERRUPTION = "workflow_interruption"

    # Specialized event types
    REASONING_CHUNK = "reasoning_chunk"  # LIVE_UI_ONLY, for the "thinking" stream
    USER_DECISION = "user_decision"  # MODEL_ONLY, for user decisions about actions


def generate_event_id() -> str:
    """Generate a unique event ID for SSE Last-Event-ID support."""
    return str(uuid.uuid4())


@dataclass
class StreamEvent:
    """Individual streaming event with unique ID for replay support."""

    event_type: Union[StreamEventType, str]
    session_id: str
    timestamp: float
    event_id: str = field(default_factory=generate_event_id)
    step_number: Optional[int] = None
    message: str = ""
    data: Optional[dict[str, Any]] = None
    progress_percent: Optional[float] = None
    tool_used: Optional[str] = None
    duration_ms: Optional[int] = None
    success: bool = True
    metadata: Optional[dict[str, Any]] = None
    visibility: EventVisibility = EventVisibility.USER_FACING

    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format with event ID for reconnection support."""
        event_type_value = (
            self.event_type.value
            if isinstance(self.event_type, StreamEventType)
            else self.event_type
        )

        event_data = {
            "type": event_type_value,
            "eventId": self.event_id,
            "sessionId": self.session_id,
            "timestamp": self.timestamp,
            "step": self.step_number,
            "message": self.message,
            "data": self.data,
            "progress": self.progress_percent,
            "tool": self.tool_used,
            "duration": self.duration_ms,
            "success": self.success,
            "visibility": self.visibility.value,
        }

        if self.metadata:
            event_data["metadata"] = self.metadata

        event_data = {k: v for k, v in event_data.items() if v is not None}

        # Include id: field for Last-Event-ID reconnection support
        return f"id: {self.event_id}\nevent: message\ndata: {json.dumps(event_data)}\n\n"

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        event_type_value = (
            self.event_type.value
            if isinstance(self.event_type, StreamEventType)
            else self.event_type
        )

        result = {
            "type": event_type_value,
            "eventId": self.event_id,
            "sessionId": self.session_id,
            "timestamp": self.timestamp,
            "message": self.message,
            "success": self.success,
            "visibility": self.visibility.value,
        }

        if self.step_number is not None:
            result["step"] = self.step_number
        if self.data is not None:
            result["data"] = self.data
        if self.progress_percent is not None:
            result["progress"] = self.progress_percent
        if self.tool_used is not None:
            result["tool"] = self.tool_used
        if self.duration_ms is not None:
            result["duration"] = self.duration_ms
        if self.metadata is not None:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamEvent":
        """Create StreamEvent from dictionary."""
        event_type = data.get("type", "")
        with contextlib.suppress(ValueError):
            event_type = StreamEventType(event_type)

        visibility = data.get("visibility", "user_facing")
        try:
            visibility = EventVisibility(visibility)
        except ValueError:
            visibility = EventVisibility.USER_FACING

        return cls(
            event_type=event_type,
            event_id=data.get("eventId", generate_event_id()),
            session_id=data.get("sessionId", ""),
            timestamp=data.get("timestamp", 0.0),
            step_number=data.get("step"),
            message=data.get("message", ""),
            data=data.get("data"),
            progress_percent=data.get("progress"),
            tool_used=data.get("tool"),
            duration_ms=data.get("duration"),
            success=data.get("success", True),
            metadata=data.get("metadata"),
            visibility=visibility,
        )
