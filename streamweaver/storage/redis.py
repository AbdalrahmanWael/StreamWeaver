"""
Redis session storage backend for StreamWeaver.

Provides production-ready distributed session storage using Redis.
"""

import json
import logging
import time
from typing import Any, Optional

from ..core.session import SessionData, SessionStore

logger = logging.getLogger(__name__)

# Try to import redis, but don't fail if it's not installed
try:
    import redis.asyncio as redis
    from redis.asyncio.connection import ConnectionPool

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.debug("redis package not installed - RedisSessionStore unavailable")


class RedisSessionStore(SessionStore):
    """
    Redis-backed session storage for production deployments.

    Features:
    - Connection pooling for high performance
    - TTL-based automatic session expiration
    - JSON serialization of session data
    - Atomic operations for consistency
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        session_timeout: int = 3600,
        key_prefix: str = "streamweaver:session:",
        pool_size: int = 10,
        db: int = 0,
    ):
        """
        Initialize Redis session store.

        Args:
            redis_url: Redis connection URL.
            session_timeout: Session TTL in seconds.
            key_prefix: Prefix for all session keys.
            pool_size: Connection pool size.
            db: Redis database number.
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package is required for RedisSessionStore. "
                "Install with: pip install streamweaver[redis]"
            )

        self.redis_url = redis_url
        self.session_timeout = session_timeout
        self.key_prefix = key_prefix
        self.pool_size = pool_size
        self.db = db

        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[redis.Redis] = None

    async def initialize(self) -> None:
        """Initialize the Redis connection pool."""
        self._pool = ConnectionPool.from_url(
            self.redis_url,
            max_connections=self.pool_size,
            db=self.db,
            decode_responses=True,
        )
        self._redis = redis.Redis(connection_pool=self._pool)
        logger.info(f"Redis session store initialized: {self.redis_url}")

        # Test connection
        try:
            await self._redis.ping()
            logger.info("Redis connection verified")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _get_key(self, session_id: str) -> str:
        """Get the Redis key for a session."""
        return f"{self.key_prefix}{session_id}"

    def _serialize_session(self, session: SessionData) -> str:
        """Serialize session data to JSON."""
        return json.dumps(
            {
                "session_id": session.session_id,
                "user_request": session.user_request,
                "context": session.context,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "status": session.status,
                "total_steps": session.total_steps,
                "completed_steps": session.completed_steps,
                "current_step": session.current_step,
                "user_id": session.user_id,
            }
        )

    def _deserialize_session(self, data: str) -> SessionData:
        """Deserialize session data from JSON."""
        parsed = json.loads(data)
        return SessionData(
            session_id=parsed["session_id"],
            user_request=parsed["user_request"],
            context=parsed.get("context", {}),
            created_at=parsed.get("created_at", time.time()),
            last_activity=parsed.get("last_activity", time.time()),
            status=parsed.get("status", "active"),
            total_steps=parsed.get("total_steps", 0),
            completed_steps=parsed.get("completed_steps", 0),
            current_step=parsed.get("current_step"),
            user_id=parsed.get("user_id"),
        )

    async def create_session(
        self,
        session_id: str,
        user_request: str,
        context: dict[str, Any],
        user_id: Optional[str] = None,
    ) -> SessionData:
        """Create a new session in Redis."""
        if self._redis is None:
            raise RuntimeError("Redis not initialized. Call initialize() first.")

        key = self._get_key(session_id)

        # Check if session exists
        if await self._redis.exists(key):
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

        # Store with TTL
        await self._redis.setex(
            key,
            self.session_timeout,
            self._serialize_session(session),
        )

        logger.info(f"Created session in Redis: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get a session from Redis."""
        if self._redis is None:
            raise RuntimeError("Redis not initialized. Call initialize() first.")

        key = self._get_key(session_id)
        data = await self._redis.get(key)

        if data is None:
            return None

        return self._deserialize_session(data)

    async def update_session(self, session_id: str, **updates) -> bool:
        """Update session data in Redis."""
        if self._redis is None:
            raise RuntimeError("Redis not initialized. Call initialize() first.")

        key = self._get_key(session_id)
        data = await self._redis.get(key)

        if data is None:
            logger.debug(f"Session {session_id} not found for update")
            return False

        session = self._deserialize_session(data)

        for field, value in updates.items():
            if hasattr(session, field):
                setattr(session, field, value)

        session.last_activity = time.time()

        # Get remaining TTL and preserve it
        ttl = await self._redis.ttl(key)
        if ttl > 0:
            await self._redis.setex(key, ttl, self._serialize_session(session))
        else:
            await self._redis.setex(key, self.session_timeout, self._serialize_session(session))

        return True

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from Redis."""
        if self._redis is None:
            raise RuntimeError("Redis not initialized. Call initialize() first.")

        key = self._get_key(session_id)
        result = await self._redis.delete(key)

        if result:
            logger.info(f"Deleted session from Redis: {session_id}")
            return True
        return False

    async def get_active_count(self) -> int:
        """Get count of active sessions."""
        if self._redis is None:
            raise RuntimeError("Redis not initialized. Call initialize() first.")

        # Count keys matching our prefix
        pattern = f"{self.key_prefix}*"
        count = 0

        async for _ in self._redis.scan_iter(match=pattern):
            count += 1

        return count

    async def get_all_session_ids(self) -> list[str]:
        """Get all active session IDs."""
        if self._redis is None:
            raise RuntimeError("Redis not initialized. Call initialize() first.")

        pattern = f"{self.key_prefix}*"
        session_ids = []

        async for key in self._redis.scan_iter(match=pattern):
            session_id = key.replace(self.key_prefix, "")
            session_ids.append(session_id)

        return session_ids

    async def extend_session(self, session_id: str, additional_seconds: int = None) -> bool:
        """Extend a session's TTL."""
        if self._redis is None:
            raise RuntimeError("Redis not initialized. Call initialize() first.")

        key = self._get_key(session_id)
        additional = additional_seconds or self.session_timeout

        if await self._redis.exists(key):
            await self._redis.expire(key, additional)
            logger.debug(f"Extended session {session_id} TTL by {additional}s")
            return True
        return False

    async def close(self) -> None:
        """Close Redis connections."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis session store closed")

        if self._pool:
            await self._pool.disconnect()
