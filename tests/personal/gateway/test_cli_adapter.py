"""Tests for CLIAdapter."""
import pytest

from cuga.personal.gateway.adapters.cli import CLIAdapter
from cuga.personal.gateway.base import DeliveryTarget, MessageEvent, MessageType


class TestCLIAdapter:
    @pytest.fixture
    def adapter(self):
        return CLIAdapter(user_id="test-user")

    def test_instantiation(self, adapter):
        assert adapter.user_id == "test-user"
        assert adapter.platform == "cli"

    @pytest.mark.asyncio
    async def test_send_writes_to_output(self, adapter, capsys):
        target = DeliveryTarget(platform="cli", channel_id="session-1")
        await adapter.send(target, "Hello from agent!")
        captured = capsys.readouterr()
        assert "Hello from agent!" in captured.out

    @pytest.mark.asyncio
    async def test_send_with_files_mentions_them(self, adapter, capsys):
        target = DeliveryTarget(platform="cli", channel_id="session-1")
        await adapter.send(target, "Done", files=[{"name": "report.pdf"}])
        captured = capsys.readouterr()
        assert "Done" in captured.out

    @pytest.mark.asyncio
    async def test_get_user_context_returns_dict(self, adapter):
        ctx = await adapter.get_user_context("test-user")
        assert isinstance(ctx, dict)

    @pytest.mark.asyncio
    async def test_stop_does_not_raise(self, adapter):
        await adapter.stop()

    @pytest.mark.asyncio
    async def test_collect_single_event(self, adapter):
        """collect_event() builds a proper MessageEvent from a text string."""
        event = adapter.collect_event("fill my timesheet")
        assert isinstance(event, MessageEvent)
        assert event.text == "fill my timesheet"
        assert event.platform == "cli"
        assert event.user_id == adapter.user_id
        assert event.type in (MessageType.TEXT, MessageType.COMMAND)

    @pytest.mark.asyncio
    async def test_collect_event_detects_command(self, adapter):
        event = adapter.collect_event("/timesheet")
        assert event.type == MessageType.COMMAND
        assert event.text == "/timesheet"
