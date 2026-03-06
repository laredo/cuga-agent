"""
Session Management system for CUGA event-driven architecture

Implements session routing and management for main/isolated execution contexts.
Enables users to control where events execute: in the main conversation thread
(context-aware) or in isolated sessions (independent execution).

Key Features:
- Main session: Context-aware execution in primary conversation thread
- Isolated sessions: Independent execution for reports, background tasks
- Session routing: Automatic routing based on event metadata
- CLI support: --session flag for user control
- Lifecycle management: Creation, tracking, cleanup of sessions
- Statistics and monitoring: Session health and activity tracking
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
import uuid

from cuga.backend.events.models import Event


class SessionType(str, Enum):
    """Types of execution sessions"""
    MAIN = "main"
    ISOLATED = "isolated"


class SessionNotFoundError(Exception):
    """Raised when a session is not found"""
    pass


class SessionConflictError(Exception):
    """Raised when attempting to create conflicting sessions"""
    pass


class SessionConfig(BaseModel):
    """
    Configuration for a session
    
    Attributes:
        session_type: Type of session (main or isolated)
        thread_id: Thread identifier for the session
        preserve_context: Whether to preserve conversation context
        timeout_seconds: Session timeout in seconds
        max_concurrent_tasks: Maximum concurrent tasks in this session
    """
    
    model_config = ConfigDict(validate_assignment=True)
    
    session_type: SessionType
    thread_id: str = "main"
    preserve_context: bool = True
    timeout_seconds: int = 3600  # 1 hour default
    max_concurrent_tasks: int = 5
    
    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout_positive(cls, v):
        """Ensure timeout is positive"""
        if v <= 0:
            raise ValueError("timeout_seconds must be positive")
        return v
    
    @field_validator('thread_id')
    @classmethod
    def validate_thread_id_for_main(cls, v, info):
        """Ensure main session has 'main' thread_id"""
        if info.data.get('session_type') == SessionType.MAIN and v != "main":
            return "main"  # Auto-correct to main
        return v


class SessionContext(BaseModel):
    """
    Context information for an active session
    
    Attributes:
        session_id: Unique session identifier
        session_type: Type of session
        thread_id: Thread identifier
        is_active: Whether session is currently active
        created_at: When session was created
        last_activity: Last activity timestamp
        metadata: Additional session metadata
    """
    
    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )
    
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_type: SessionType
    thread_id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def update_activity(self) -> None:
        """Update the last activity timestamp"""
        self.last_activity = datetime.now(timezone.utc)
    
    def deactivate(self) -> None:
        """Deactivate this session"""
        self.is_active = False
    
    def is_expired(self, timeout_seconds: int) -> bool:
        """
        Check if session has expired
        
        Args:
            timeout_seconds: Timeout threshold in seconds
            
        Returns:
            True if session is expired, False otherwise
        """
        if not self.is_active:
            return True
        
        elapsed = datetime.now(timezone.utc) - self.last_activity
        return elapsed.total_seconds() > timeout_seconds


class SessionManager:
    """
    Manages session lifecycle and tracking
    
    The SessionManager handles creation, retrieval, and cleanup of sessions.
    It ensures only one main session exists and tracks all isolated sessions.
    
    Example:
        >>> manager = SessionManager()
        >>> main_session = manager.create_session(session_type=SessionType.MAIN)
        >>> task_session = manager.create_session(
        ...     session_type=SessionType.ISOLATED,
        ...     thread_id="report-task"
        ... )
    """
    
    def __init__(self):
        """Initialize the session manager"""
        self.sessions: Dict[str, SessionContext] = {}
        self.main_session: Optional[SessionContext] = None
    
    def create_session(
        self,
        session_type: SessionType,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionContext:
        """
        Create a new session
        
        Args:
            session_type: Type of session to create
            thread_id: Optional thread identifier
            metadata: Optional session metadata
            
        Returns:
            Created session context
            
        Raises:
            SessionConflictError: If attempting to create duplicate main session
        """
        # Check for main session conflict
        if session_type == SessionType.MAIN and self.main_session is not None:
            raise SessionConflictError("Main session already exists")
        
        # Set default thread_id
        if thread_id is None:
            if session_type == SessionType.MAIN:
                thread_id = "main"
            else:
                thread_id = f"isolated-{str(uuid.uuid4())[:8]}"
        
        # Create session context
        session = SessionContext(
            session_type=session_type,
            thread_id=thread_id,
            metadata=metadata or {}
        )
        
        # Store session
        self.sessions[session.session_id] = session
        
        # Track main session
        if session_type == SessionType.MAIN:
            self.main_session = session
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """
        Get a session by ID
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session context if found, None otherwise
        """
        return self.sessions.get(session_id)
    
    def get_session_by_thread_id(self, thread_id: str) -> Optional[SessionContext]:
        """
        Get a session by thread ID
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Session context if found, None otherwise
        """
        for session in self.sessions.values():
            if session.thread_id == thread_id:
                return session
        return None
    
    def get_main_session(self) -> Optional[SessionContext]:
        """
        Get the main session
        
        Returns:
            Main session context if exists, None otherwise
        """
        return self.main_session
    
    def close_session(self, session_id: str) -> None:
        """
        Close a session
        
        Args:
            session_id: Session identifier
            
        Raises:
            SessionNotFoundError: If session not found
        """
        session = self.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")
        
        session.deactivate()
        
        # Clear main session reference if closing main
        if session.session_type == SessionType.MAIN:
            self.main_session = None
    
    def cleanup_expired_sessions(self, timeout_seconds: int = 3600) -> int:
        """
        Clean up expired sessions
        
        Args:
            timeout_seconds: Timeout threshold in seconds
            
        Returns:
            Number of sessions cleaned up
        """
        expired_ids = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired(timeout_seconds):
                expired_ids.append(session_id)
        
        # Remove expired sessions
        for session_id in expired_ids:
            del self.sessions[session_id]
        
        return len(expired_ids)
    
    def get_active_sessions(self) -> List[SessionContext]:
        """
        Get all active sessions
        
        Returns:
            List of active session contexts
        """
        return [s for s in self.sessions.values() if s.is_active]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get session statistics
        
        Returns:
            Dictionary containing statistics
        """
        active_sessions = self.get_active_sessions()
        inactive_sessions = [s for s in self.sessions.values() if not s.is_active]
        isolated_sessions = [s for s in self.sessions.values() if s.session_type == SessionType.ISOLATED]
        
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": len(active_sessions),
            "inactive_sessions": len(inactive_sessions),
            "main_session_active": self.main_session is not None and self.main_session.is_active,
            "isolated_sessions": len(isolated_sessions)
        }


class SessionRouter:
    """
    Routes events to appropriate sessions
    
    The SessionRouter determines which session should handle an event based on
    event metadata, type, and routing rules. It can create sessions on-demand.
    
    Example:
        >>> manager = SessionManager()
        >>> router = SessionRouter(manager=manager)
        >>> session = router.route_event(event)
    """
    
    def __init__(self, manager: SessionManager):
        """
        Initialize the session router
        
        Args:
            manager: Session manager instance
        """
        self.manager = manager
    
    def route_event(self, event: Event) -> SessionContext:
        """
        Route an event to the appropriate session
        
        Args:
            event: Event to route
            
        Returns:
            Session context for handling the event
        """
        # Determine session type from event
        session_type = self.determine_session_type(event)
        
        # Get thread_id from metadata
        thread_id = event.metadata.get("thread_id")
        
        # Get or create session
        session = self.get_or_create_session(
            session_type=session_type,
            thread_id=thread_id
        )
        
        # Update activity
        session.update_activity()
        
        return session
    
    def determine_session_type(self, event: Event) -> SessionType:
        """
        Determine session type from event
        
        Args:
            event: Event to analyze
            
        Returns:
            Determined session type
        """
        # Check explicit session_target in metadata
        session_target = event.metadata.get("session_target")
        if session_target:
            if session_target == "main":
                return SessionType.MAIN
            elif session_target == "isolated":
                return SessionType.ISOLATED
        
        # Heartbeat events always go to main
        if event.type == "heartbeat":
            return SessionType.MAIN
        
        # Default to main for interactive events
        return SessionType.MAIN
    
    def get_or_create_session(
        self,
        session_type: SessionType,
        thread_id: Optional[str] = None
    ) -> SessionContext:
        """
        Get existing session or create new one
        
        Args:
            session_type: Type of session
            thread_id: Optional thread identifier
            
        Returns:
            Session context
        """
        # For main session, return existing or create
        if session_type == SessionType.MAIN:
            main_session = self.manager.get_main_session()
            if main_session and main_session.is_active:
                return main_session
            return self.manager.create_session(session_type=SessionType.MAIN)
        
        # For isolated session, check if exists by thread_id
        if thread_id:
            existing = self.manager.get_session_by_thread_id(thread_id)
            if existing and existing.is_active:
                return existing
        
        # Create new isolated session
        return self.manager.create_session(
            session_type=SessionType.ISOLATED,
            thread_id=thread_id
        )

# Made with Bob
