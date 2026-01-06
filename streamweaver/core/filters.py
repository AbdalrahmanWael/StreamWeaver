"""
Event filtering for StreamWeaver.

Allows filtering events by visibility, type, or custom criteria
before they're sent to clients.
"""

import logging
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Set, Union

from .events import EventVisibility, StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


class EventFilter(ABC):
    """Abstract base class for event filters."""

    @abstractmethod
    def should_include(self, event: StreamEvent) -> bool:
        """
        Determine if an event should be included in the stream.
        
        Args:
            event: The event to check.
            
        Returns:
            True if the event should be included, False to filter it out.
        """
        pass

    def __and__(self, other: "EventFilter") -> "CompositeFilter":
        """Combine filters with AND logic."""
        return CompositeFilter([self, other], operator="and")

    def __or__(self, other: "EventFilter") -> "CompositeFilter":
        """Combine filters with OR logic."""
        return CompositeFilter([self, other], operator="or")

    def __invert__(self) -> "NotFilter":
        """Invert the filter."""
        return NotFilter(self)


class VisibilityFilter(EventFilter):
    """Filter events by their visibility level."""

    def __init__(self, visibilities: Union[EventVisibility, List[EventVisibility]]):
        """
        Initialize the visibility filter.
        
        Args:
            visibilities: One or more visibility levels to include.
        """
        if isinstance(visibilities, EventVisibility):
            visibilities = [visibilities]
        self.visibilities: Set[EventVisibility] = set(visibilities)

    def should_include(self, event: StreamEvent) -> bool:
        return event.visibility in self.visibilities

    def __repr__(self) -> str:
        return f"VisibilityFilter({[v.value for v in self.visibilities]})"


class TypeFilter(EventFilter):
    """Filter events by their event type."""

    def __init__(
        self,
        event_types: Union[StreamEventType, str, List[Union[StreamEventType, str]]],
        include: bool = True,
    ):
        """
        Initialize the type filter.
        
        Args:
            event_types: One or more event types to match.
            include: If True, include matching events. If False, exclude them.
        """
        if isinstance(event_types, (StreamEventType, str)):
            event_types = [event_types]

        self.event_types: Set[str] = set()
        for et in event_types:
            if isinstance(et, StreamEventType):
                self.event_types.add(et.value)
            else:
                self.event_types.add(et)

        self.include = include

    def should_include(self, event: StreamEvent) -> bool:
        event_type_value = (
            event.event_type.value
            if isinstance(event.event_type, StreamEventType)
            else event.event_type
        )
        matches = event_type_value in self.event_types
        return matches if self.include else not matches

    def __repr__(self) -> str:
        mode = "include" if self.include else "exclude"
        return f"TypeFilter({list(self.event_types)}, {mode})"


class CompositeFilter(EventFilter):
    """Combine multiple filters with AND or OR logic."""

    def __init__(self, filters: List[EventFilter], operator: str = "and"):
        """
        Initialize the composite filter.
        
        Args:
            filters: List of filters to combine.
            operator: Either "and" or "or".
        """
        self.filters = filters
        self.operator = operator.lower()
        if self.operator not in ("and", "or"):
            raise ValueError(f"Operator must be 'and' or 'or', got '{operator}'")

    def should_include(self, event: StreamEvent) -> bool:
        if self.operator == "and":
            return all(f.should_include(event) for f in self.filters)
        else:  # or
            return any(f.should_include(event) for f in self.filters)

    def __repr__(self) -> str:
        return f"CompositeFilter({self.filters}, {self.operator})"


class NotFilter(EventFilter):
    """Invert another filter's result."""

    def __init__(self, filter_to_invert: EventFilter):
        self.inner_filter = filter_to_invert

    def should_include(self, event: StreamEvent) -> bool:
        return not self.inner_filter.should_include(event)

    def __repr__(self) -> str:
        return f"NotFilter({self.inner_filter})"


class CallableFilter(EventFilter):
    """Filter using a custom callable."""

    def __init__(self, predicate: Callable[[StreamEvent], bool]):
        """
        Initialize the callable filter.
        
        Args:
            predicate: A function that takes an event and returns True to include it.
        """
        self.predicate = predicate

    def should_include(self, event: StreamEvent) -> bool:
        return self.predicate(event)

    def __repr__(self) -> str:
        return f"CallableFilter({self.predicate.__name__})"


class SessionFilter(EventFilter):
    """Filter events by session ID."""

    def __init__(self, session_ids: Union[str, List[str]], include: bool = True):
        """
        Initialize the session filter.
        
        Args:
            session_ids: One or more session IDs to match.
            include: If True, include matching events. If False, exclude them.
        """
        if isinstance(session_ids, str):
            session_ids = [session_ids]
        self.session_ids: Set[str] = set(session_ids)
        self.include = include

    def should_include(self, event: StreamEvent) -> bool:
        matches = event.session_id in self.session_ids
        return matches if self.include else not matches

    def __repr__(self) -> str:
        mode = "include" if self.include else "exclude"
        return f"SessionFilter({list(self.session_ids)}, {mode})"


# Pre-built filter instances for common use cases
USER_FACING_FILTER = VisibilityFilter(EventVisibility.USER_FACING)
LIVE_UI_FILTER = VisibilityFilter([EventVisibility.USER_FACING, EventVisibility.LIVE_UI_ONLY])
NO_HEARTBEAT_FILTER = TypeFilter(StreamEventType.HEARTBEAT, include=False)
PROGRESS_ONLY_FILTER = TypeFilter([
    StreamEventType.WORKFLOW_STARTED,
    StreamEventType.STEP_STARTED,
    StreamEventType.STEP_PROGRESS,
    StreamEventType.STEP_COMPLETED,
    StreamEventType.WORKFLOW_COMPLETED,
])


def apply_filter(events: List[StreamEvent], filter_: Optional[EventFilter]) -> List[StreamEvent]:
    """
    Apply a filter to a list of events.
    
    Args:
        events: List of events to filter.
        filter_: The filter to apply, or None to include all events.
        
    Returns:
        Filtered list of events.
    """
    if filter_ is None:
        return events
    return [e for e in events if filter_.should_include(e)]
