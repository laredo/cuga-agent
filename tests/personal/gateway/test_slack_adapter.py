"""Tests for SlackAdapter (mocked slack_bolt)."""
import pytest
from unittest.mock import AsyncMock

from cuga.personal.gateway.base import DeliveryTarget, MessageType


class TestSlackAdapterEventParsing:
    """Test the Slack event → MessageEvent conversion logic."""

    def test_parse_regular_message(self):
        from cuga.personal.gateway.adapters.slack import SlackAdapter

        raw = {
            "type": "message",
            "user": "U123",
            "text": "fill my timesheet",
            "channel": "C456",
            "ts": "1712345678.000001",
            "event_ts": "1712345678.000001",
        }
        event = SlackAdapter.parse_event(raw)
        assert event.user_id == "U123"
        assert event.channel_id == "C456"
        assert event.text == "fill my timesheet"
        assert event.type == MessageType.TEXT
        assert event.platform == "slack"

    def test_parse_slash_command(self):
        from cuga.personal.gateway.adapters.slack import SlackAdapter

        raw = {
            "type": "message",
            "user": "U123",
            "text": "/timesheet",
            "channel": "C456",
            "ts": "1712345678.000001",
            "event_ts": "1712345678.000001",
        }
        event = SlackAdapter.parse_event(raw)
        assert event.type == MessageType.COMMAND

    def test_parse_threaded_message(self):
        from cuga.personal.gateway.adapters.slack import SlackAdapter

        raw = {
            "type": "message",
            "user": "U123",
            "text": "follow up",
            "channel": "C456",
            "ts": "1712345679.000001",
            "thread_ts": "1712345678.000001",
            "event_ts": "1712345679.000001",
        }
        event = SlackAdapter.parse_event(raw)
        assert event.thread_id == "1712345678.000001"

    def test_parse_message_with_files(self):
        from cuga.personal.gateway.adapters.slack import SlackAdapter

        raw = {
            "type": "message",
            "user": "U123",
            "text": "expense receipts",
            "channel": "C456",
            "ts": "1712345678.000001",
            "event_ts": "1712345678.000001",
            "files": [{"id": "F001", "name": "receipt.pdf", "url_private": "http://x"}],
        }
        event = SlackAdapter.parse_event(raw)
        assert event.type == MessageType.FILE
        assert len(event.files) == 1
        assert event.files[0]["name"] == "receipt.pdf"


class TestSlackAdapterSend:
    @pytest.mark.asyncio
    async def test_send_calls_client(self):
        from cuga.personal.gateway.adapters.slack import SlackAdapter

        mock_client = AsyncMock()
        adapter = SlackAdapter.__new__(SlackAdapter)
        adapter._client = mock_client
        adapter.platform = "slack"

        target = DeliveryTarget(platform="slack", channel_id="C123")
        await adapter.send(target, "Hello!")
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["text"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_to_thread(self):
        from cuga.personal.gateway.adapters.slack import SlackAdapter

        mock_client = AsyncMock()
        adapter = SlackAdapter.__new__(SlackAdapter)
        adapter._client = mock_client
        adapter.platform = "slack"

        target = DeliveryTarget(platform="slack", channel_id="C123", thread_id="T456")
        await adapter.send(target, "Reply in thread")
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["thread_ts"] == "T456"
