"""Tests for session management."""

import asyncio
import pytest
import time

from streamweaver import SessionData, InMemorySessionStore


class TestSessionData:
    """Tests for SessionData dataclass."""

    def test_create_session_data(self):
        """Test creating session data."""
        session = SessionData(
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
        assert session.total_steps == 0
        assert session.completed_steps == 0

    def test_session_timestamps(self):
        """Test that session timestamps are set."""
        before = time.time()
        session = SessionData(
            session_id="test",
            user_request="Test",
        )
        after = time.time()
        
        assert before <= session.created_at <= after
        assert before <= session.last_activity <= after


class TestInMemorySessionStore:
    """Tests for InMemorySessionStore."""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test store initialization."""
        store = InMemorySessionStore()
        await store.initialize()
        
        count = await store.get_active_count()
        assert count == 0
        
        await store.close()

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a session."""
        store = InMemorySessionStore()
        await store.initialize()
        
        session = await store.create_session(
            session_id="test-1",
            user_request="Hello",
            context={"key": "value"},
            user_id="user-123",
        )
        
        assert session.session_id == "test-1"
        assert session.user_request == "Hello"
        assert session.context == {"key": "value"}
        assert session.user_id == "user-123"
        
        await store.close()

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting a session."""
        store = InMemorySessionStore()
        await store.initialize()
        
        await store.create_session("test-1", "Request", {})
        
        session = await store.get_session("test-1")
        assert session is not None
        assert session.session_id == "test-1"
        
        await store.close()

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Test getting a session that doesn't exist."""
        store = InMemorySessionStore()
        await store.initialize()
        
        session = await store.get_session("nonexistent")
        assert session is None
        
        await store.close()

    @pytest.mark.asyncio
    async def test_update_session(self):
        """Test updating a session."""
        store = InMemorySessionStore()
        await store.initialize()
        
        await store.create_session("test-1", "Request", {})
        
        success = await store.update_session(
            "test-1",
            status="processing",
            current_step="Step 1",
            completed_steps=1,
        )
        assert success is True
        
        session = await store.get_session("test-1")
        assert session.status == "processing"
        assert session.current_step == "Step 1"
        assert session.completed_steps == 1
        
        await store.close()

    @pytest.mark.asyncio
    async def test_update_nonexistent_session(self):
        """Test updating a session that doesn't exist."""
        store = InMemorySessionStore()
        await store.initialize()
        
        success = await store.update_session(
            "nonexistent",
            status="completed",
        )
        assert success is False
        
        await store.close()

    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test deleting a session."""
        store = InMemorySessionStore()
        await store.initialize()
        
        await store.create_session("test-1", "Request", {})
        
        success = await store.delete_session("test-1")
        assert success is True
        
        session = await store.get_session("test-1")
        assert session is None
        
        await store.close()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self):
        """Test deleting a session that doesn't exist."""
        store = InMemorySessionStore()
        await store.initialize()
        
        success = await store.delete_session("nonexistent")
        assert success is False
        
        await store.close()

    @pytest.mark.asyncio
    async def test_get_active_count(self):
        """Test counting active sessions."""
        store = InMemorySessionStore()
        await store.initialize()
        
        assert await store.get_active_count() == 0
        
        await store.create_session("test-1", "Request 1", {})
        assert await store.get_active_count() == 1
        
        await store.create_session("test-2", "Request 2", {})
        assert await store.get_active_count() == 2
        
        await store.delete_session("test-1")
        assert await store.get_active_count() == 1
        
        await store.close()

    @pytest.mark.asyncio
    async def test_overwrite_existing_session(self):
        """Test that creating a session with existing ID overwrites it."""
        store = InMemorySessionStore()
        await store.initialize()
        
        await store.create_session("test-1", "Original", {"v": 1})
        await store.create_session("test-1", "Updated", {"v": 2})
        
        session = await store.get_session("test-1")
        assert session.user_request == "Updated"
        assert session.context == {"v": 2}
        
        await store.close()

    @pytest.mark.asyncio
    async def test_update_sets_last_activity(self):
        """Test that update sets last_activity timestamp."""
        store = InMemorySessionStore()
        await store.initialize()
        
        session = await store.create_session("test-1", "Request", {})
        original_activity = session.last_activity
        
        await asyncio.sleep(0.1)
        await store.update_session("test-1", status="processing")
        
        session = await store.get_session("test-1")
        assert session.last_activity > original_activity
        
        await store.close()

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Test store with custom session timeout."""
        store = InMemorySessionStore(session_timeout=60, cleanup_interval=30)
        await store.initialize()
        
        assert store.session_timeout == 60
        assert store.cleanup_interval == 30
        
        await store.close()

    @pytest.mark.asyncio
    async def test_close_cleanup_task(self):
        """Test that close properly cancels cleanup task."""
        store = InMemorySessionStore()
        await store.initialize()
        
        # Verify cleanup task is running
        assert store._cleanup_task is not None
        assert not store._cleanup_task.done()
        
        await store.close()
        
        # Task should be cancelled
        assert store._cleanup_task.done()
