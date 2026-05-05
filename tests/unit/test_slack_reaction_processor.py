"""
Unit tests for Slack reaction handling in SlackEventProcessor.
Covers reaction_added / reaction_removed dispatch and the three
reaction semantics: approve (👍), reject (👎), and unrecognized.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cuga.backend.events.models import Event, EventType, EventSource
from cuga.backend.events.session_management import SessionContext, SessionType
from cuga.backend.integrations.slack.processor import SlackEventProcessor


def make_reaction_event(
    reaction: str,
    event_name: str = "reaction_added",
    item_user: str = "U999",
    channel: str = "C456",
    item_ts: str = "1234567890.000100",
) -> Event:
    return Event(
        type=EventType.SLACK,
        source=EventSource.WEBHOOK,
        event_name=event_name,
        payload={
            "reaction": reaction,
            "user": "U123",
            "item": {"type": "message", "channel": channel, "ts": item_ts},
            "item_user": item_user,
        },
        metadata={
            "session_target": "isolated",
            "slack_team_id": "T001",
            "slack_event_id": "Ev001",
        },
    )


def make_session_context() -> SessionContext:
    return SessionContext(
        session_id="sess-001",
        session_type=SessionType.ISOLATED,
        thread_id="isolated-001",
    )


@pytest.fixture
def mock_notification():
    channel = MagicMock()
    channel.send_response = AsyncMock()
    return channel


@pytest.fixture
def processor(mock_notification):
    return SlackEventProcessor(notification_channel=mock_notification, cuga_enabled=False)


class TestReactionRouting:
    """process_event() dispatches both reaction event names to _handle_reaction."""

    async def test_reaction_added_dispatched(self, processor):
        event = make_reaction_event("+1", event_name="reaction_added")
        session = make_session_context()
        with patch.object(processor, "_handle_reaction", new=AsyncMock()) as mock_handler:
            await processor.process_event(event, session)
            mock_handler.assert_awaited_once_with(event, session)

    async def test_reaction_removed_dispatched(self, processor):
        event = make_reaction_event("+1", event_name="reaction_removed")
        session = make_session_context()
        with patch.object(processor, "_handle_reaction", new=AsyncMock()) as mock_handler:
            await processor.process_event(event, session)
            mock_handler.assert_awaited_once_with(event, session)


class TestReactionApprove:
    """+1 / thumbsup / white_check_mark reactions send an approval acknowledgment."""

    @pytest.mark.parametrize("emoji", ["+1", "thumbsup", "white_check_mark"])
    async def test_approve_emoji_sends_response(self, processor, mock_notification, emoji):
        event = make_reaction_event(emoji)
        session = make_session_context()
        await processor._handle_reaction(event, session)
        mock_notification.send_response.assert_awaited_once()
        call_kwargs = mock_notification.send_response.call_args
        assert "approved" in call_kwargs.kwargs.get("text", "").lower()

    async def test_approval_targets_original_message_channel(self, processor, mock_notification):
        event = make_reaction_event("+1", channel="C456")
        session = make_session_context()
        await processor._handle_reaction(event, session)
        call_kwargs = mock_notification.send_response.call_args
        assert call_kwargs.kwargs.get("channel") == "C456"

    async def test_approval_threads_on_original_message(self, processor, mock_notification):
        event = make_reaction_event("+1", item_ts="9999.0001")
        session = make_session_context()
        await processor._handle_reaction(event, session)
        call_kwargs = mock_notification.send_response.call_args
        assert call_kwargs.kwargs.get("thread_ts") == "9999.0001"


class TestReactionReject:
    """-1 / thumbsdown / x reactions send a rejection acknowledgment."""

    @pytest.mark.parametrize("emoji", ["-1", "thumbsdown", "x"])
    async def test_reject_emoji_sends_response(self, processor, mock_notification, emoji):
        event = make_reaction_event(emoji)
        session = make_session_context()
        await processor._handle_reaction(event, session)
        mock_notification.send_response.assert_awaited_once()
        call_kwargs = mock_notification.send_response.call_args
        assert "rejected" in call_kwargs.kwargs.get("text", "").lower()

    async def test_rejection_targets_original_message_channel(self, processor, mock_notification):
        event = make_reaction_event("-1", channel="C789")
        session = make_session_context()
        await processor._handle_reaction(event, session)
        call_kwargs = mock_notification.send_response.call_args
        assert call_kwargs.kwargs.get("channel") == "C789"


class TestReactionUnrecognized:
    """Unrecognized emojis produce no Slack response — silently logged."""

    @pytest.mark.parametrize("emoji", ["eyes", "wave", "fire", "rocket", "tada"])
    async def test_unknown_emoji_sends_no_response(self, processor, mock_notification, emoji):
        event = make_reaction_event(emoji)
        session = make_session_context()
        await processor._handle_reaction(event, session)
        mock_notification.send_response.assert_not_awaited()


class TestReactionRemoved:
    """Removing any reaction produces no Slack response."""

    async def test_removing_approval_reaction_sends_no_response(self, processor, mock_notification):
        event = make_reaction_event("+1", event_name="reaction_removed")
        session = make_session_context()
        await processor._handle_reaction(event, session)
        mock_notification.send_response.assert_not_awaited()

    async def test_removing_reject_reaction_sends_no_response(self, processor, mock_notification):
        event = make_reaction_event("-1", event_name="reaction_removed")
        session = make_session_context()
        await processor._handle_reaction(event, session)
        mock_notification.send_response.assert_not_awaited()


class TestReactionMalformedPayload:
    """Handler is robust to missing or incomplete payload fields."""

    async def test_missing_reaction_field_does_not_raise(self, processor):
        event = Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="reaction_added",
            payload={},
            metadata={"session_target": "isolated"},
        )
        session = make_session_context()
        await processor._handle_reaction(event, session)

    async def test_missing_item_field_does_not_raise(self, processor):
        event = Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="reaction_added",
            payload={"reaction": "+1", "user": "U123"},
            metadata={"session_target": "isolated"},
        )
        session = make_session_context()
        await processor._handle_reaction(event, session)

    async def test_missing_channel_in_item_does_not_raise(self, processor):
        event = Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="reaction_added",
            payload={
                "reaction": "+1",
                "user": "U123",
                "item": {"type": "message"},  # no channel
            },
            metadata={"session_target": "isolated"},
        )
        session = make_session_context()
        await processor._handle_reaction(event, session)
