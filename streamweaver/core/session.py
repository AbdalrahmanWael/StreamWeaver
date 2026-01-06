"""
Session management for StreamWeaver.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """Data stored for a workflow session"""

    session_id: str
    user_request: str
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    status: str = "active"
    total_steps: int = 0
    completed_steps: int = 0
    current_step: Optional[str] = None
    user_id: Optional[str] = None


class SessionStore(ABC):
    """Abstract base class for session storage backends"""

    @abstractmethod
    async def create_session(
        self,
        session_id: str,
        user_request: str,
        context: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> SessionData:
        """Create a new session"""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get a session by ID"""
        pass

    @abstractmethod
    async def update_session(self, session_id: str, **updates) -> bool:
        """Update session data"""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        pass

    @abstractmethod
    async def get_active_count(self) -> int:
        """Get count of active sessions"""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session storage for development and testing"""

    def __init__(self, session_timeout: int = 3600, cleanup_interval: int = 300):
        self.sessions: Dict[str, SessionData] = {}
        self.session_timeout = session_timeout
        self.cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the session store"""
        logger.info("In-memory session store initialized")
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())

    async def create_session(
        self,
        session_id: str,
        user_request: str,
        context: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> SessionData:
        """Create a new session"""
        if session_id in self.sessions:
            logger.warning(f"Session {session_id} already exists. Overwriting.")

        now = time.time()
        session = SessionData(
            session_id=session_id,
            user_request=user_request,
            context=context,
            created_at=now,
            last_activity=now,
            user_id=user_id,
        )
        self.sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get a session by ID"""
        return self.sessions.get(session_id)

    async def update_session(self, session_id: str, **updates) -> bool:
        """Update session data"""
        session = self.sessions.get(session_id)
        if not session:
            logger.debug(f"Session {session_id} not found for update")
            return False

        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        session.last_activity = time.time()
        return True

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session = self.sessions.pop(session_id, None)
        if session:
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    async def get_active_count(self) -> int:
        """Get count of active sessions"""
        return len(self.sessions)

    async def _cleanup_expired_sessions(self):
        """Background task to cleanup expired sessions"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                current_time = time.time()
                expired_sessions = []

                for session_id, session in self.sessions.items():
                    if current_time - session.last_activity > self.session_timeout:
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    await self.delete_session(session_id)

                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

            except Exception as e:
                logger.error(f"Error during session cleanup: {e}")

    async def close(self):
        """Cleanup resources"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
