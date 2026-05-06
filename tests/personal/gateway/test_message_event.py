"""Tests for MessageEvent, DeliveryTarget, and gateway base models."""
from datetime import datetime, timezone

from cuga.personal.gateway.base import MessageEvent, MessageType, DeliveryTarget


class TestMessageEvent:
    def test_minimal_creation(self):
        event = MessageEvent(
            id="evt-1",
            channel_id="chan-1",
            user_id="user-1",
            platform="cli",
            type=MessageType.TEXT,
            text="hello",
            timestamp=datetime.now(timezone.utc),
        )
        assert event.id == "evt-1"
        assert event.platform == "cli"
        assert event.files == []
        assert event.thread_id is None
        assert event.metadata == {}

    def test_full_creation(self):
        ts = datetime(2026, 4, 5, 10, 0, 0, tzinfo=timezone.utc)
        event = MessageEvent(
            id="evt-2",
            channel_id="C123",
            user_id="U456",
            platform="slack",
            type=MessageType.COMMAND,
            text="/timesheet",
            files=[{"name": "receipt.pdf", "url": "http://example.com/f.pdf"}],
            thread_id="T789",
            timestamp=ts,
            metadata={"workspace": "W001"},
        )
        assert event.type == MessageType.COMMAND
        assert len(event.files) == 1
        assert event.thread_id == "T789"
        assert event.metadata["workspace"] == "W001"

    def test_serialization_roundtrip(self):
        ts = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
        event = MessageEvent(
            id="evt-3",
            channel_id="chan-x",
            user_id="user-x",
            platform="email",
            type=MessageType.FILE,
            text="See attached",
            timestamp=ts,
        )
        data = event.model_dump()
        restored = MessageEvent.model_validate(data)
        assert restored.id == event.id
        assert restored.type == event.type
        assert restored.timestamp == event.timestamp

    def test_message_type_values(self):
        assert MessageType.TEXT == "text"
        assert MessageType.FILE == "file"
        assert MessageType.IMAGE == "image"
        assert MessageType.COMMAND == "command"

    def test_invalid_platform_still_allowed(self):
        """Platform is a free-form string — no enum restriction."""
        event = MessageEvent(
            id="x",
            channel_id="c",
            user_id="u",
            platform="teams",
            type=MessageType.TEXT,
            text="hi",
            timestamp=datetime.now(timezone.utc),
        )
        assert event.platform == "teams"


class TestDeliveryTarget:
    def test_minimal_creation(self):
        target = DeliveryTarget(platform="cli", channel_id="session-1")
        assert target.platform == "cli"
        assert target.thread_id is None
        assert target.user_id is None

    def test_full_creation(self):
        target = DeliveryTarget(
            platform="slack",
            channel_id="C123",
            thread_id="T456",
            user_id="U789",
        )
        assert target.thread_id == "T456"
        assert target.user_id == "U789"
