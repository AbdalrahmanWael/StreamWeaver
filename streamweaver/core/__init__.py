"""
Core components for StreamWeaver.
"""

from .backpressure import BackpressurePolicy, BackpressureQueue
from .batching import BatchConfig, BatcherPool, EventBatcher
from .events import EventVisibility, StreamEvent, StreamEventType, generate_event_id
from .filters import (
    LIVE_UI_FILTER,
    NO_HEARTBEAT_FILTER,
    PROGRESS_ONLY_FILTER,
    USER_FACING_FILTER,
    CallableFilter,
    CompositeFilter,
    EventFilter,
    NotFilter,
    SessionFilter,
    TypeFilter,
    VisibilityFilter,
    apply_filter,
)
from .generator import StreamGenerator
from .metrics import StreamWeaverMetrics, get_metrics, init_metrics
from .replay import EventBuffer, SessionEventBuffers
from .schemas import (
    AgentMessageData,
    ErrorData,
    StepCompletedData,
    StepFailedData,
    StepProgressData,
    StepStartedData,
    ToolCompletedData,
    ToolExecutedData,
    WorkflowCompletedData,
    WorkflowStartedData,
    create_error,
    create_step_progress,
    create_tool_executed,
    create_workflow_started,
    validate_event_data,
)
from .service import StreamWeaver, StreamWeaverConfig
from .session import InMemorySessionStore, SessionData, SessionStore

__all__ = [
    # Events
    "StreamEvent",
    "StreamEventType",
    "EventVisibility",
    "generate_event_id",
    # Session
    "SessionData",
    "SessionStore",
    "InMemorySessionStore",
    # Service
    "StreamWeaver",
    "StreamWeaverConfig",
    # Generator
    "StreamGenerator",
    # Backpressure
    "BackpressurePolicy",
    "BackpressureQueue",
    # Replay
    "EventBuffer",
    "SessionEventBuffers",
    # Filters
    "EventFilter",
    "VisibilityFilter",
    "TypeFilter",
    "CompositeFilter",
    "NotFilter",
    "CallableFilter",
    "SessionFilter",
    "apply_filter",
    "USER_FACING_FILTER",
    "LIVE_UI_FILTER",
    "NO_HEARTBEAT_FILTER",
    "PROGRESS_ONLY_FILTER",
    # Metrics
    "StreamWeaverMetrics",
    "get_metrics",
    "init_metrics",
    # Batching
    "EventBatcher",
    "BatcherPool",
    "BatchConfig",
    # Schemas
    "WorkflowStartedData",
    "WorkflowCompletedData",
    "StepStartedData",
    "StepProgressData",
    "StepCompletedData",
    "StepFailedData",
    "ToolExecutedData",
    "ToolCompletedData",
    "ErrorData",
    "AgentMessageData",
    "validate_event_data",
    "create_workflow_started",
    "create_step_progress",
    "create_tool_executed",
    "create_error",
]
