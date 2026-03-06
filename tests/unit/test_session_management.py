"""
Unit tests for Session Management system
Following TDD approach - tests for main/isolated session routing with CLI support
"""
import pytest
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from cuga.backend.events.session_management import (
    SessionType,
    SessionConfig,
    SessionContext,
    SessionManager,
    SessionRouter,
    SessionNotFoundError,
    SessionConflictError
)
from cuga.backend.events.models import Event, EventType, EventSource


class TestSessionType:
    """Test SessionType enum"""
    
    def test_session_type_values(self):
        """Test all session types are defined"""
        assert SessionType.MAIN == "main"
        assert SessionType.ISOLATED == "isolated"
    
    def test_session_type_membership(self):
        """Test session type membership"""
        assert "main" in [s.value for s in SessionType]
        assert "isolated" in [s.value for s in SessionType]


class TestSessionConfig:
    """Test SessionConfig model"""
    
    def test_session_config_creation_with_defaults(self):
        """Test creating session config with default values"""
        config = SessionConfig(
            session_type=SessionType.MAIN
        )
        
        assert config.session_type == SessionType.MAIN
        assert config.thread_id == "main"
        assert config.preserve_context is True
        assert config.timeout_seconds == 3600
        assert config.max_concurrent_tasks == 5
    
    def test_session_config_isolated_session(self):
        """Test creating isolated session config"""
        config = SessionConfig(
            session_type=SessionType.ISOLATED,
            thread_id="task-123",
            preserve_context=False
        )
        
        assert config.session_type == SessionType.ISOLATED
        assert config.thread_id == "task-123"
        assert config.preserve_context is False
    
    def test_session_config_main_must_have_main_thread_id(self):
        """Test that main session must have 'main' thread_id"""
        config = SessionConfig(
            session_type=SessionType.MAIN,
            thread_id="main"
        )
        
        assert config.thread_id == "main"
    
    def test_session_config_isolated_can_have_custom_thread_id(self):
        """Test that isolated session can have custom thread_id"""
        config = SessionConfig(
            session_type=SessionType.ISOLATED,
            thread_id="custom-thread-456"
        )
        
        assert config.thread_id == "custom-thread-456"
    
    def test_session_config_validation_timeout_positive(self):
        """Test that timeout must be positive"""
        with pytest.raises(Exception):  # Validation error
            SessionConfig(
                session_type=SessionType.MAIN,
                timeout_seconds=-1
            )


class TestSessionContext:
    """Test SessionContext model"""
    
    def test_session_context_creation(self):
        """Test creating a session context"""
        context = SessionContext(
            session_id="session-123",
            session_type=SessionType.MAIN,
            thread_id="main"
        )
        
        assert context.session_id == "session-123"
        assert context.session_type == SessionType.MAIN
        assert context.thread_id == "main"
        assert context.is_active is True
        assert isinstance(context.created_at, datetime)
        assert context.last_activity is not None
        assert context.metadata == {}
    
    def test_session_context_with_metadata(self):
        """Test creating context with metadata"""
        metadata = {"user_id": "user-123", "task": "email_check"}
        context = SessionContext(
            session_id="session-456",
            session_type=SessionType.ISOLATED,
            thread_id="task-456",
            metadata=metadata
        )
        
        assert context.metadata == metadata
    
    def test_session_context_update_activity(self):
        """Test updating last activity timestamp"""
        context = SessionContext(
            session_id="session-789",
            session_type=SessionType.MAIN,
            thread_id="main"
        )
        
        original_activity = context.last_activity
        context.update_activity()
        
        assert context.last_activity > original_activity
    
    def test_session_context_deactivate(self):
        """Test deactivating a session"""
        context = SessionContext(
            session_id="session-999",
            session_type=SessionType.MAIN,
            thread_id="main"
        )
        
        assert context.is_active is True
        context.deactivate()
        assert context.is_active is False
    
    def test_session_context_is_expired(self):
        """Test checking if session is expired"""
        context = SessionContext(
            session_id="session-exp",
            session_type=SessionType.ISOLATED,
            thread_id="task-exp"
        )
        
        # Fresh session should not be expired
        assert context.is_expired(timeout_seconds=3600) is False
        
        # Manually set old last_activity
        from datetime import timedelta
        context.last_activity = datetime.now(timezone.utc) - timedelta(seconds=7200)
        
        # Should be expired now
        assert context.is_expired(timeout_seconds=3600) is True


class TestSessionManager:
    """Test SessionManager functionality"""
    
    def test_session_manager_creation(self):
        """Test creating a session manager"""
        manager = SessionManager()
        
        assert len(manager.sessions) == 0
        assert manager.main_session is None
    
    def test_create_main_session(self):
        """Test creating the main session"""
        manager = SessionManager()
        
        session = manager.create_session(
            session_type=SessionType.MAIN
        )
        
        assert session.session_type == SessionType.MAIN
        assert session.thread_id == "main"
        assert session.is_active is True
        assert manager.main_session == session
    
    def test_create_isolated_session(self):
        """Test creating an isolated session"""
        manager = SessionManager()
        
        session = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-123"
        )
        
        assert session.session_type == SessionType.ISOLATED
        assert session.thread_id == "task-123"
        assert session.is_active is True
    
    def test_create_multiple_isolated_sessions(self):
        """Test creating multiple isolated sessions"""
        manager = SessionManager()
        
        session1 = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-1"
        )
        session2 = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-2"
        )
        
        assert len(manager.sessions) == 2
        assert session1.session_id != session2.session_id
    
    def test_cannot_create_multiple_main_sessions(self):
        """Test that only one main session can exist"""
        manager = SessionManager()
        
        manager.create_session(session_type=SessionType.MAIN)
        
        with pytest.raises(SessionConflictError):
            manager.create_session(session_type=SessionType.MAIN)
    
    def test_get_session_by_id(self):
        """Test retrieving a session by ID"""
        manager = SessionManager()
        
        session = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-get"
        )
        
        retrieved = manager.get_session(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_get_nonexistent_session_returns_none(self):
        """Test that getting nonexistent session returns None"""
        manager = SessionManager()
        
        result = manager.get_session("nonexistent-id")
        
        assert result is None
    
    def test_get_session_by_thread_id(self):
        """Test retrieving a session by thread ID"""
        manager = SessionManager()
        
        session = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-thread"
        )
        
        retrieved = manager.get_session_by_thread_id("task-thread")
        
        assert retrieved is not None
        assert retrieved.thread_id == "task-thread"
    
    def test_get_main_session(self):
        """Test retrieving the main session"""
        manager = SessionManager()
        
        created = manager.create_session(session_type=SessionType.MAIN)
        retrieved = manager.get_main_session()
        
        assert retrieved is not None
        assert retrieved.session_id == created.session_id
    
    def test_close_session(self):
        """Test closing a session"""
        manager = SessionManager()
        
        session = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-close"
        )
        
        assert session.is_active is True
        
        manager.close_session(session.session_id)
        
        assert session.is_active is False
    
    def test_close_nonexistent_session_raises_error(self):
        """Test that closing nonexistent session raises error"""
        manager = SessionManager()
        
        with pytest.raises(SessionNotFoundError):
            manager.close_session("nonexistent-id")
    
    def test_cleanup_expired_sessions(self):
        """Test cleaning up expired sessions"""
        manager = SessionManager()
        
        # Create sessions
        session1 = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-1"
        )
        session2 = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-2"
        )
        
        # Manually expire session1
        from datetime import timedelta
        session1.last_activity = datetime.now(timezone.utc) - timedelta(seconds=7200)
        
        # Cleanup with 1 hour timeout
        cleaned = manager.cleanup_expired_sessions(timeout_seconds=3600)
        
        assert cleaned == 1
        assert len(manager.sessions) == 1
        assert session2.session_id in manager.sessions
    
    def test_get_active_sessions(self):
        """Test getting all active sessions"""
        manager = SessionManager()
        
        session1 = manager.create_session(
            session_type=SessionType.MAIN
        )
        session2 = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-1"
        )
        session3 = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-2"
        )
        
        # Close one session
        manager.close_session(session3.session_id)
        
        active = manager.get_active_sessions()
        
        assert len(active) == 2
        assert all(s.is_active for s in active)
    
    def test_get_statistics(self):
        """Test getting session statistics"""
        manager = SessionManager()
        
        manager.create_session(session_type=SessionType.MAIN)
        manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-1"
        )
        session3 = manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-2"
        )
        manager.close_session(session3.session_id)
        
        stats = manager.get_statistics()
        
        assert stats["total_sessions"] == 3
        assert stats["active_sessions"] == 2
        assert stats["inactive_sessions"] == 1
        assert stats["main_session_active"] is True
        assert stats["isolated_sessions"] == 2


class TestSessionRouter:
    """Test SessionRouter functionality"""
    
    def test_session_router_creation(self):
        """Test creating a session router"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        assert router.manager == manager
    
    def test_route_event_to_main_session(self):
        """Test routing event to main session"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        # Create main session
        manager.create_session(session_type=SessionType.MAIN)
        
        event = Event(
            type=EventType.HEARTBEAT,
            source=EventSource.SCHEDULER,
            event_name="heartbeat_check",
            payload={},
            metadata={"session_target": "main"}
        )
        
        session = router.route_event(event)
        
        assert session is not None
        assert session.session_type == SessionType.MAIN
    
    def test_route_event_to_isolated_session(self):
        """Test routing event to isolated session"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        # Create isolated session
        manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-123"
        )
        
        event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="daily_report",
            payload={},
            metadata={"session_target": "isolated", "thread_id": "task-123"}
        )
        
        session = router.route_event(event)
        
        assert session is not None
        assert session.session_type == SessionType.ISOLATED
        assert session.thread_id == "task-123"
    
    def test_route_event_creates_session_if_not_exists(self):
        """Test that routing creates session if it doesn't exist"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="task",
            payload={},
            metadata={"session_target": "isolated", "thread_id": "new-task"}
        )
        
        session = router.route_event(event)
        
        assert session is not None
        assert session.thread_id == "new-task"
    
    def test_route_event_default_to_main(self):
        """Test that events without session_target default to main"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        # Create main session
        manager.create_session(session_type=SessionType.MAIN)
        
        event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="pull_request",
            payload={}
        )
        
        session = router.route_event(event)
        
        assert session is not None
        assert session.session_type == SessionType.MAIN
    
    def test_determine_session_type_from_event(self):
        """Test determining session type from event"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        # Heartbeat should go to main
        heartbeat_event = Event(
            type=EventType.HEARTBEAT,
            source=EventSource.SCHEDULER,
            event_name="heartbeat",
            payload={}
        )
        assert router.determine_session_type(heartbeat_event) == SessionType.MAIN
        
        # Cron with isolated target
        cron_event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="report",
            payload={},
            metadata={"session_target": "isolated"}
        )
        assert router.determine_session_type(cron_event) == SessionType.ISOLATED
    
    def test_get_or_create_session(self):
        """Test getting or creating a session"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        # First call should create
        session1 = router.get_or_create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-get-create"
        )
        
        assert session1 is not None
        
        # Second call should return existing
        session2 = router.get_or_create_session(
            session_type=SessionType.ISOLATED,
            thread_id="task-get-create"
        )
        
        assert session2.session_id == session1.session_id


class TestSessionIntegration:
    """Integration tests for session management"""
    
    def test_full_session_lifecycle(self):
        """Test complete session lifecycle"""
        manager = SessionManager()
        router = SessionRouter(manager=manager)
        
        # Create main session
        main_session = manager.create_session(session_type=SessionType.MAIN)
        assert main_session.is_active
        
        # Route heartbeat to main
        heartbeat_event = Event(
            type=EventType.HEARTBEAT,
            source=EventSource.SCHEDULER,
            event_name="heartbeat",
            payload={}
        )
        routed_session = router.route_event(heartbeat_event)
        assert routed_session.session_id == main_session.session_id
        
        # Create isolated session for task
        task_event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="report",
            payload={},
            metadata={"session_target": "isolated", "thread_id": "report-task"}
        )
        task_session = router.route_event(task_event)
        assert task_session.session_type == SessionType.ISOLATED
        
        # Verify statistics
        stats = manager.get_statistics()
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 2
        
        # Close task session
        manager.close_session(task_session.session_id)
        assert not task_session.is_active
        
        # Main session should still be active
        assert main_session.is_active

# Made with Bob
