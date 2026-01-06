"""StreamWeaver - Enterprise-grade Server-Sent Events for agentic workflows"""

__version__ = "0.2.0"

# Core exports
# Backpressure
from .core.backpressure import BackpressurePolicy, BackpressureQueue

# Batching
from .core.batching import BatchConfig, BatcherPool, EventBatcher
from .core.events import EventVisibility, StreamEvent, StreamEventType, generate_event_id

# Filters
from .core.filters import (
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
from .core.generator import StreamGenerator

# Metrics
from .core.metrics import StreamWeaverMetrics, get_metrics, init_metrics

# Replay
from .core.replay import EventBuffer, SessionEventBuffers

# Schemas
from .core.schemas import (
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
from .core.service import StreamWeaver, StreamWeaverConfig
from .core.session import InMemorySessionStore, SessionData, SessionStore

__all__ = [
    # Version
    "__version__",
    # Core
    "StreamEvent",
    "StreamEventType",
    "EventVisibility",
    "generate_event_id",
    "SessionData",
    "SessionStore",
    "InMemorySessionStore",
    "StreamWeaver",
    "StreamWeaverConfig",
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
