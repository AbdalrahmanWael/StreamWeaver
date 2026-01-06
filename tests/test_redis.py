"""Tests for Redis session storage."""

import pytest
import time

# Skip all tests if redis is not available
pytest.importorskip("redis")

from streamweaver.storage.redis import RedisSessionStore, REDIS_AVAILABLE


# Skip entire module if redis is not available
pytestmark = pytest.mark.skipif(
    not REDIS_AVAILABLE,
    reason="redis package not installed"
)


@pytest.fixture
async def redis_store():
    """Create a Redis session store for testing."""
    # Use a unique prefix to avoid conflicts
    store = RedisSessionStore(
        redis_url="redis://localhost:6379",
        session_timeout=60,
        key_prefix=f"test:streamweaver:{time.time()}:",
        db=15,  # Use a separate database for tests
    )
    
    try:
        await store.initialize()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
    
    try:
        yield store
    finally:
        # Cleanup: delete all test keys
        if store._redis:
            try:
                async for key in store._redis.scan_iter(match=f"{store.key_prefix}*"):
                    await store._redis.delete(key)
                await store.close()
            except Exception:
                pass


class TestRedisSessionStore:
    """Tests for RedisSessionStore."""

    @pytest.mark.asyncio
    async def test_create_session(self, redis_store):
        """Test creating a session in Redis."""
        session = await redis_store.create_session(
            session_id="test-1",
            user_request="Hello",
            context={"key": "value"},
            user_id="user-123",
        )
        
        assert session.session_id == "test-1"
        assert session.user_request == "Hello"
        assert session.context == {"key": "value"}
        assert session.user_id == "user-123"
        assert session.status == "active"

    @pytest.mark.asyncio
    async def test_get_session(self, redis_store):
        """Test retrieving a session from Redis."""
        await redis_store.create_session(
            session_id="test-2",
            user_request="Test request",
            context={},
        )
        
        session = await redis_store.get_session("test-2")
        
        assert session is not None
        assert session.session_id == "test-2"
        assert session.user_request == "Test request"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, redis_store):
        """Test getting a session that doesn't exist."""
        session = await redis_store.get_session("nonexistent")
        
        assert session is None

    @pytest.mark.asyncio
    async def test_update_session(self, redis_store):
        """Test updating session data."""
        await redis_store.create_session(
            session_id="test-3",
            user_request="Initial",
            context={},
        )
        
        success = await redis_store.update_session(
            "test-3",
            status="processing",
            current_step="Step 1",
            completed_steps=1,
        )
        
        assert success is True
        
        session = await redis_store.get_session("test-3")
        assert session.status == "processing"
        assert session.current_step == "Step 1"
        assert session.completed_steps == 1

    @pytest.mark.asyncio
    async def test_update_nonexistent_session(self, redis_store):
        """Test updating a session that doesn't exist."""
        success = await redis_store.update_session(
            "nonexistent",
            status="completed",
        )
        
        assert success is False

    @pytest.mark.asyncio
    async def test_delete_session(self, redis_store):
        """Test deleting a session."""
        await redis_store.create_session(
            session_id="test-4",
            user_request="To delete",
            context={},
        )
        
        success = await redis_store.delete_session("test-4")
        assert success is True
        
        session = await redis_store.get_session("test-4")
        assert session is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, redis_store):
        """Test deleting a session that doesn't exist."""
        success = await redis_store.delete_session("nonexistent")
        
        assert success is False

    @pytest.mark.asyncio
    async def test_get_active_count(self, redis_store):
        """Test counting active sessions."""
        initial_count = await redis_store.get_active_count()
        
        await redis_store.create_session("count-1", "Request 1", {})
        await redis_store.create_session("count-2", "Request 2", {})
        await redis_store.create_session("count-3", "Request 3", {})
        
        count = await redis_store.get_active_count()
        
        assert count == initial_count + 3

    @pytest.mark.asyncio
    async def test_get_all_session_ids(self, redis_store):
        """Test getting all session IDs."""
        await redis_store.create_session("list-1", "Request 1", {})
        await redis_store.create_session("list-2", "Request 2", {})
        
        session_ids = await redis_store.get_all_session_ids()
        
        assert "list-1" in session_ids
        assert "list-2" in session_ids

    @pytest.mark.asyncio
    async def test_extend_session(self, redis_store):
        """Test extending a session's TTL."""
        await redis_store.create_session(
            session_id="extend-1",
            user_request="To extend",
            context={},
        )
        
        success = await redis_store.extend_session("extend-1", 7200)
        
        assert success is True

    @pytest.mark.asyncio
    async def test_extend_nonexistent_session(self, redis_store):
        """Test extending a session that doesn't exist."""
        success = await redis_store.extend_session("nonexistent", 7200)
        
        assert success is False

    @pytest.mark.asyncio
    async def test_session_with_complex_context(self, redis_store):
        """Test session with complex nested context."""
        context = {
            "user": {"name": "Test", "preferences": {"theme": "dark"}},
            "history": [1, 2, 3],
            "nested": {"deep": {"value": True}},
        }
        
        await redis_store.create_session(
            session_id="complex-1",
            user_request="Complex context",
            context=context,
        )
        
        session = await redis_store.get_session("complex-1")
        
        assert session.context == context

    @pytest.mark.asyncio
    async def test_overwrite_existing_session(self, redis_store):
        """Test that creating a session with existing ID overwrites it."""
        await redis_store.create_session(
            session_id="overwrite-1",
            user_request="Original",
            context={"version": 1},
        )
        
        await redis_store.create_session(
            session_id="overwrite-1",
            user_request="Updated",
            context={"version": 2},
        )
        
        session = await redis_store.get_session("overwrite-1")
        
        assert session.user_request == "Updated"
        assert session.context == {"version": 2}
