"""
Event models for CUGA event system

Defines core event types, sources, and the Event model with support for:
- Multiple event types (GitHub, Slack, Cron, Heartbeat, Custom)
- Event sources (Webhook, Scheduler, Internal)
- Priority levels
- Retry logic
- Metadata and state management
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import uuid


class EventType(str, Enum):
    """Types of events supported by CUGA"""
    GITHUB = "github"
    SLACK = "slack"
    CRON = "cron"
    HEARTBEAT = "heartbeat"  # Batched periodic monitoring
    CUSTOM = "custom"
    AGENT = "agent"  # Inter-agent messages via AgentBus


class EventSource(str, Enum):
    """Sources from which events originate"""
    WEBHOOK = "webhook"
    SCHEDULER = "scheduler"
    INTERNAL = "internal"


class EventPriority(str, Enum):
    """Priority levels for event processing"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Event(BaseModel):
    """
    Unified event model for all event types
    
    Attributes:
        id: Unique event identifier (auto-generated UUID)
        type: Type of event (github, slack, cron, heartbeat, custom)
        source: Source of the event (webhook, scheduler, internal)
        event_name: Specific name of the event (e.g., "pull_request", "app_mention")
        payload: Event-specific data
        metadata: Additional metadata for the event
        priority: Processing priority (low, normal, high, urgent)
        created_at: Timestamp when event was created
        processed_at: Timestamp when event was processed (None if not yet processed)
        status: Current status (pending, processing, completed, failed, rejected)
        retry_count: Number of times event processing has been retried
        max_retries: Maximum number of retry attempts allowed
    
    Example:
        >>> event = Event(
        ...     type=EventType.GITHUB,
        ...     source=EventSource.WEBHOOK,
        ...     event_name="pull_request",
        ...     payload={"action": "opened", "number": 123}
        ... )
        >>> event.status
        'pending'
        >>> event.retry_count
        0
    """
    
    # Required fields
    type: EventType
    source: EventSource
    event_name: str
    payload: Dict[str, Any]
    
    # Optional fields with defaults
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    status: str = "pending"
    retry_count: int = 0
    max_retries: int = 3
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={datetime: lambda v: v.isoformat()}
    )
    
    def __str__(self) -> str:
        """String representation of event"""
        return f"Event(id={self.id[:8]}, type={self.type}, name={self.event_name}, status={self.status})"
    
    def __repr__(self) -> str:
        """Detailed representation of event"""
        return (
            f"Event(id='{self.id}', type={self.type}, source={self.source}, "
            f"event_name='{self.event_name}', status='{self.status}', "
            f"retry_count={self.retry_count})"
        )

# Made with Bob
