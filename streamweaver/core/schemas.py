"""
Typed event schemas for StreamWeaver.

Provides Pydantic models for validated event payloads with better
IDE autocomplete and type safety.
"""

from typing import Any, Optional, Union

from pydantic import BaseModel


class BaseEventData(BaseModel):
    """Base class for event data payloads."""

    class Config:
        extra = "allow"  # Allow additional fields


class WorkflowStartedData(BaseEventData):
    """Data for WORKFLOW_STARTED events."""

    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    total_steps: Optional[int] = None
    context: Optional[dict[str, Any]] = None


class WorkflowCompletedData(BaseEventData):
    """Data for WORKFLOW_COMPLETED events."""

    workflow_id: Optional[str] = None
    total_duration_ms: Optional[int] = None
    result: Optional[Any] = None
    summary: Optional[str] = None


class StepStartedData(BaseEventData):
    """Data for STEP_STARTED events."""

    step_id: Optional[str] = None
    step_name: Optional[str] = None
    step_description: Optional[str] = None


class StepProgressData(BaseEventData):
    """Data for STEP_PROGRESS events."""

    step_id: Optional[str] = None
    progress_message: Optional[str] = None
    items_processed: Optional[int] = None
    items_total: Optional[int] = None


class StepCompletedData(BaseEventData):
    """Data for STEP_COMPLETED events."""

    step_id: Optional[str] = None
    duration_ms: Optional[int] = None
    result: Optional[Any] = None


class StepFailedData(BaseEventData):
    """Data for STEP_FAILED events."""

    step_id: Optional[str] = None
    error_message: str
    error_code: Optional[str] = None
    error_details: Optional[dict[str, Any]] = None
    recoverable: bool = False


class ToolExecutedData(BaseEventData):
    """Data for TOOL_EXECUTED events."""

    tool_name: str
    tool_input: Optional[dict[str, Any]] = None
    tool_description: Optional[str] = None


class ToolCompletedData(BaseEventData):
    """Data for TOOL_COMPLETED events."""

    tool_name: str
    tool_output: Optional[Any] = None
    duration_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None


class ErrorData(BaseEventData):
    """Data for ERROR events."""

    error_message: str
    error_code: Optional[str] = None
    error_type: Optional[str] = None
    error_details: Optional[dict[str, Any]] = None
    recoverable: bool = False
    retry_after_ms: Optional[int] = None


class AgentMessageData(BaseEventData):
    """Data for AGENT_MESSAGE events."""

    content: str
    role: str = "assistant"
    model: Optional[str] = None
    finish_reason: Optional[str] = None


class TokenChunkData(BaseEventData):
    """Data for TOKEN_CHUNK events (streaming LLM output)."""

    content: str
    token_count: Optional[int] = None
    is_final: bool = False


class ReasoningChunkData(BaseEventData):
    """Data for REASONING_CHUNK events (thinking/reasoning output)."""

    content: str
    reasoning_step: Optional[int] = None


class UserDecisionData(BaseEventData):
    """Data for USER_DECISION events."""

    decision_type: str  # e.g., "approve", "reject", "modify"
    decision_value: Optional[Any] = None
    decision_context: Optional[dict[str, Any]] = None


class HeartbeatData(BaseEventData):
    """Data for HEARTBEAT events."""

    sequence: Optional[int] = None
    server_time: Optional[float] = None


# Type alias for any event data
EventData = Union[
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
    TokenChunkData,
    ReasoningChunkData,
    UserDecisionData,
    HeartbeatData,
    dict[str, Any],
]


# Mapping from event type to data schema
EVENT_TYPE_SCHEMAS: dict[str, type] = {
    "workflow_started": WorkflowStartedData,
    "workflow_completed": WorkflowCompletedData,
    "step_started": StepStartedData,
    "step_progress": StepProgressData,
    "step_completed": StepCompletedData,
    "step_failed": StepFailedData,
    "tool_executed": ToolExecutedData,
    "tool_completed": ToolCompletedData,
    "error": ErrorData,
    "agent_message": AgentMessageData,
    "token_chunk": TokenChunkData,
    "reasoning_chunk": ReasoningChunkData,
    "user_decision": UserDecisionData,
    "heartbeat": HeartbeatData,
}


def validate_event_data(
    event_type: str,
    data: Optional[dict[str, Any]],
    strict: bool = False,
) -> Optional[dict[str, Any]]:
    """
    Validate event data against the schema for its event type.

    Args:
        event_type: The event type to validate against.
        data: The data to validate.
        strict: If True, raises ValueError on validation failure.
                If False, returns data as-is on failure.

    Returns:
        Validated data as a dictionary.

    Raises:
        ValueError: If strict=True and validation fails.
    """
    if data is None:
        return None

    schema = EVENT_TYPE_SCHEMAS.get(event_type)
    if schema is None:
        return data  # No schema defined for this type

    try:
        validated = schema(**data)
        return validated.model_dump(exclude_none=True)
    except Exception as e:
        if strict:
            raise ValueError(f"Invalid data for event type '{event_type}': {e}") from e
        return data


def create_workflow_started(
    workflow_id: Optional[str] = None,
    workflow_name: Optional[str] = None,
    total_steps: Optional[int] = None,
    **kwargs,
) -> dict[str, Any]:
    """Helper to create WorkflowStartedData."""
    return WorkflowStartedData(
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        total_steps=total_steps,
        **kwargs,
    ).model_dump(exclude_none=True)


def create_step_progress(
    step_id: Optional[str] = None,
    progress_message: Optional[str] = None,
    items_processed: Optional[int] = None,
    items_total: Optional[int] = None,
    **kwargs,
) -> dict[str, Any]:
    """Helper to create StepProgressData."""
    return StepProgressData(
        step_id=step_id,
        progress_message=progress_message,
        items_processed=items_processed,
        items_total=items_total,
        **kwargs,
    ).model_dump(exclude_none=True)


def create_tool_executed(
    tool_name: str,
    tool_input: Optional[dict[str, Any]] = None,
    tool_description: Optional[str] = None,
    **kwargs,
) -> dict[str, Any]:
    """Helper to create ToolExecutedData."""
    return ToolExecutedData(
        tool_name=tool_name,
        tool_input=tool_input,
        tool_description=tool_description,
        **kwargs,
    ).model_dump(exclude_none=True)


def create_error(
    error_message: str,
    error_code: Optional[str] = None,
    error_type: Optional[str] = None,
    recoverable: bool = False,
    **kwargs,
) -> dict[str, Any]:
    """Helper to create ErrorData."""
    return ErrorData(
        error_message=error_message,
        error_code=error_code,
        error_type=error_type,
        recoverable=recoverable,
        **kwargs,
    ).model_dump(exclude_none=True)
