"""Tests for SessionManager."""
import pytest
from datetime import datetime, timezone

from cuga.personal.gateway.base import MessageEvent, MessageType
from cuga.personal.gateway.session import Session, SessionManager


def _make_event(user_id="user-1", platform="cli", thread_id=None):
    return MessageEvent(
        id="evt-1",
        channel_id="chan-1",
        user_id=user_id,
        platform=platform,
        type=MessageType.TEXT,
        text="hello",
        thread_id=thread_id,
        timestamp=datetime.now(timezone.utc),
    )


class TestSession:
    def test_creation(self):
        session = Session(user_id="user-1", platform="cli", thread_id="t-abc")
        assert session.user_id == "user-1"
        assert session.platform == "cli"
        assert session.thread_id == "t-abc"
        assert session.user_context == {}
        assert session.active_skill is None


class TestSessionManager:
    @pytest.fixture
    def manager(self):
        return SessionManager()

    @pytest.mark.asyncio
    async def test_creates_session_for_new_user(self, manager):
        event = _make_event(user_id="user-1", platform="cli")
        session = await manager.get_or_create_session(event)
        assert session.user_id == "user-1"
        assert session.platform == "cli"
        assert session.thread_id is not None

    @pytest.mark.asyncio
    async def test_returns_same_session_for_same_user(self, manager):
        event = _make_event(user_id="user-1", platform="cli")
        s1 = await manager.get_or_create_session(event)
        s2 = await manager.get_or_create_session(event)
        assert s1.thread_id == s2.thread_id

    @pytest.mark.asyncio
    async def test_different_users_get_different_sessions(self, manager):
        e1 = _make_event(user_id="user-1", platform="slack")
        e2 = _make_event(user_id="user-2", platform="slack")
        s1 = await manager.get_or_create_session(e1)
        s2 = await manager.get_or_create_session(e2)
        assert s1.thread_id != s2.thread_id

    @pytest.mark.asyncio
    async def test_same_user_different_platforms_get_different_sessions(self, manager):
        e1 = _make_event(user_id="user-1", platform="slack")
        e2 = _make_event(user_id="user-1", platform="cli")
        s1 = await manager.get_or_create_session(e1)
        s2 = await manager.get_or_create_session(e2)
        assert s1.thread_id != s2.thread_id

    @pytest.mark.asyncio
    async def test_reset_session_creates_new_thread(self, manager):
        event = _make_event(user_id="user-1", platform="cli")
        s1 = await manager.get_or_create_session(event)
        old_thread = s1.thread_id
        await manager.reset_session(user_id="user-1", platform="cli")
        s2 = await manager.get_or_create_session(event)
        assert s2.thread_id != old_thread

    @pytest.mark.asyncio
    async def test_event_thread_id_is_respected(self, manager):
        """If the inbound event already carries a thread_id, reuse it."""
        event = _make_event(user_id="user-1", platform="slack", thread_id="existing-thread")
        session = await manager.get_or_create_session(event)
        assert session.thread_id == "existing-thread"
