"""
Unit tests for Event models
Following TDD approach - these tests will fail until we implement the models
"""
import pytest
from datetime import datetime, timezone
from cuga.backend.events.models import Event, EventType, EventSource, EventPriority


class TestEventType:
    """Test EventType enum"""
    
    def test_event_type_values(self):
        """Test all event types are defined"""
        assert EventType.GITHUB == "github"
        assert EventType.SLACK == "slack"
        assert EventType.CRON == "cron"
        assert EventType.HEARTBEAT == "heartbeat"
        assert EventType.CUSTOM == "custom"
    
    def test_event_type_membership(self):
        """Test event type membership"""
        assert "github" in [e.value for e in EventType]
        assert "heartbeat" in [e.value for e in EventType]


class TestEventSource:
    """Test EventSource enum"""
    
    def test_event_source_values(self):
        """Test all event sources are defined"""
        assert EventSource.WEBHOOK == "webhook"
        assert EventSource.SCHEDULER == "scheduler"
        assert EventSource.INTERNAL == "internal"


class TestEventPriority:
    """Test EventPriority enum"""
    
    def test_event_priority_values(self):
        """Test all priority levels are defined"""
        assert EventPriority.LOW == "low"
        assert EventPriority.NORMAL == "normal"
        assert EventPriority.HIGH == "high"
        assert EventPriority.URGENT == "urgent"


class TestEventModel:
    """Test Event model creation and validation"""
    
    def test_event_creation_with_defaults(self):
        """Test creating event with default values"""
        event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="pull_request",
            payload={"action": "opened"}
        )
        
        # Check required fields
        assert event.type == EventType.GITHUB
        assert event.source == EventSource.WEBHOOK
        assert event.event_name == "pull_request"
        assert event.payload == {"action": "opened"}
        
        # Check defaults
        assert event.id is not None
        assert len(event.id) > 0
        assert event.status == "pending"
        assert event.retry_count == 0
        assert event.max_retries == 3
        assert event.priority == EventPriority.NORMAL
        assert isinstance(event.created_at, datetime)
        assert event.processed_at is None
        assert event.metadata == {}
    
    def test_event_creation_with_custom_values(self):
        """Test creating event with custom values"""
        custom_time = datetime.now(timezone.utc)
        event = Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="app_mention",
            payload={"text": "Hello"},
            metadata={"channel": "general", "user": "alice"},
            priority=EventPriority.HIGH,
            status="processing",
            retry_count=1,
            max_retries=5,
            created_at=custom_time
        )
        
        assert event.type == EventType.SLACK
        assert event.metadata["channel"] == "general"
        assert event.metadata["user"] == "alice"
        assert event.priority == EventPriority.HIGH
        assert event.status == "processing"
        assert event.retry_count == 1
        assert event.max_retries == 5
        assert event.created_at == custom_time
    
    def test_event_heartbeat_type(self):
        """Test creating heartbeat event"""
        event = Event(
            type=EventType.HEARTBEAT,
            source=EventSource.SCHEDULER,
            event_name="heartbeat",
            payload={
                "tasks": ["email", "calendar"],
                "session_target": "main",
                "thread_id": "main"
            },
            metadata={"batched": True, "task_count": 2}
        )
        
        assert event.type == EventType.HEARTBEAT
        assert event.source == EventSource.SCHEDULER
        assert event.payload["session_target"] == "main"
        assert event.metadata["batched"] is True
    
    def test_event_serialization(self):
        """Test event can be serialized to dict"""
        event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="daily_summary",
            payload={"message": "Run summary"}
        )
        
        event_dict = event.model_dump()
        
        assert isinstance(event_dict, dict)
        assert event_dict["type"] == "cron"
        assert event_dict["source"] == "scheduler"
        assert event_dict["event_name"] == "daily_summary"
        assert "id" in event_dict
        assert "created_at" in event_dict
    
    def test_event_json_serialization(self):
        """Test event can be serialized to JSON"""
        event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="push",
            payload={"commits": 3}
        )
        
        json_str = event.model_dump_json()
        assert isinstance(json_str, str)
        assert "github" in json_str
        assert "webhook" in json_str
    
    def test_event_validation_requires_type(self):
        """Test event validation fails without type"""
        with pytest.raises(ValueError):
            Event(
                source=EventSource.WEBHOOK,
                event_name="test",
                payload={}
            )
    
    def test_event_validation_requires_source(self):
        """Test event validation fails without source"""
        with pytest.raises(ValueError):
            Event(
                type=EventType.CUSTOM,
                event_name="test",
                payload={}
            )
    
    def test_event_validation_requires_event_name(self):
        """Test event validation fails without event_name"""
        with pytest.raises(ValueError):
            Event(
                type=EventType.CUSTOM,
                source=EventSource.WEBHOOK,
                payload={}
            )
    
    def test_event_validation_requires_payload(self):
        """Test event validation fails without payload"""
        with pytest.raises(ValueError):
            Event(
                type=EventType.CUSTOM,
                source=EventSource.WEBHOOK,
                event_name="test"
            )
    
    def test_event_invalid_type(self):
        """Test event validation fails with invalid type"""
        with pytest.raises(ValueError):
            Event(
                type="invalid_type",
                source=EventSource.WEBHOOK,
                event_name="test",
                payload={}
            )
    
    def test_event_invalid_source(self):
        """Test event validation fails with invalid source"""
        with pytest.raises(ValueError):
            Event(
                type=EventType.CUSTOM,
                source="invalid_source",
                event_name="test",
                payload={}
            )
    
    def test_event_id_is_unique(self):
        """Test each event gets a unique ID"""
        event1 = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test1",
            payload={}
        )
        
        event2 = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test2",
            payload={}
        )
        
        assert event1.id != event2.id
    
    def test_event_status_transitions(self):
        """Test event status can be updated"""
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={}
        )
        
        assert event.status == "pending"
        
        event.status = "processing"
        assert event.status == "processing"
        
        event.status = "completed"
        assert event.status == "completed"
    
    def test_event_retry_count_increment(self):
        """Test retry count can be incremented"""
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={}
        )
        
        assert event.retry_count == 0
        
        event.retry_count += 1
        assert event.retry_count == 1
        
        event.retry_count += 1
        assert event.retry_count == 2
    
    def test_event_processed_at_can_be_set(self):
        """Test processed_at timestamp can be set"""
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={}
        )
        
        assert event.processed_at is None
        
        processed_time = datetime.now(timezone.utc)
        event.processed_at = processed_time
        
        assert event.processed_at == processed_time
    
    def test_event_metadata_can_be_updated(self):
        """Test metadata can be updated"""
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={}
        )
        
        assert event.metadata == {}
        
        event.metadata["key1"] = "value1"
        assert event.metadata["key1"] == "value1"
        
        event.metadata["key2"] = "value2"
        assert len(event.metadata) == 2
    
    def test_event_comparison(self):
        """Test events can be compared by ID"""
        event1 = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={}
        )
        
        event2 = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={}
        )
        
        # Different events should not be equal
        assert event1.id != event2.id
        
        # Same event should be equal to itself
        assert event1.id == event1.id

# Made with Bob
