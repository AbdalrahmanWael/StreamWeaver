"""StreamWeaver - Enterprise-grade Server-Sent Events for agentic workflows"""

__version__ = "0.2.0"

# Core exports
from .core.events import EventVisibility, StreamEvent, StreamEventType, generate_event_id
from .core.session import InMemorySessionStore, SessionData, SessionStore
from .core.service import StreamWeaver, StreamWeaverConfig
from .core.generator import StreamGenerator

# Backpressure
from .core.backpressure import BackpressurePolicy, BackpressureQueue

# Replay
from .core.replay import EventBuffer, SessionEventBuffers

# Filters
from .core.filters import (
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

# Metrics
from .core.metrics import StreamWeaverMetrics, get_metrics, init_metrics

# Batching
from .core.batching import EventBatcher, BatcherPool, BatchConfig

# Schemas
from .core.schemas import (
    WorkflowStartedData,
    WorkflowCompletedData,
    StepStartedData,
    StepProgressData,
    StepCompletedData,
    StepFailedData,
    ToolExecutedData,
    ToolCompletedData,
    ErrorData,
    AgentMessageData,
    validate_event_data,
    create_workflow_started,
    create_step_progress,
    create_tool_executed,
    create_error,
)

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
