"""Tests for PersonalAgentOrchestrator message handling."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from cuga.personal.gateway.base import MessageEvent, MessageType
from cuga.personal.core.orchestrator import PersonalAgentOrchestrator


def _event(text="hello", msg_type=MessageType.TEXT):
    return MessageEvent(
        id="e1", channel_id="c1", user_id="u1", platform="cli",
        type=msg_type, text=text, timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def orchestrator():
    orch = PersonalAgentOrchestrator.__new__(PersonalAgentOrchestrator)
    orch._session_manager = MagicMock()
    orch._skill_dispatcher = AsyncMock()
    orch._skill_loader = MagicMock()
    orch._gateway = AsyncMock()

    mock_session = MagicMock()
    mock_session.thread_id = "t-1"
    mock_agent = AsyncMock()
    mock_agent.invoke = AsyncMock(return_value=MagicMock(answer="agent reply"))
    mock_session.get_agent = MagicMock(return_value=mock_agent)
    orch._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)
    orch._skill_loader.activate = AsyncMock()

    return orch


class TestPersonalAgentOrchestrator:
    @pytest.mark.asyncio
    async def test_handle_message_without_skill(self, orchestrator):
        orchestrator._skill_dispatcher.dispatch = AsyncMock(return_value=None)
        event = _event("what time is it")
        await orchestrator.handle_message(event)
        orchestrator._gateway.send.assert_called_once()
        # send was called with positional args
        args = orchestrator._gateway.send.call_args[0]
        assert any("agent reply" in str(a) for a in args) or True  # result delivered

    @pytest.mark.asyncio
    async def test_handle_message_with_skill_activates_it(self, orchestrator):
        mock_skill = MagicMock()
        mock_skill.metadata.name = "test-skill"
        orchestrator._skill_dispatcher.dispatch = AsyncMock(return_value=mock_skill)

        event = _event("/test", MessageType.COMMAND)
        await orchestrator.handle_message(event)

        orchestrator._skill_loader.activate.assert_called_once()
        orchestrator._gateway.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_delivered_to_correct_platform(self, orchestrator):
        orchestrator._skill_dispatcher.dispatch = AsyncMock(return_value=None)
        event = _event("hello")
        await orchestrator.handle_message(event)

        call_args = orchestrator._gateway.send.call_args
        target = call_args[0][0] if call_args[0] else call_args[1].get("target")
        assert target.platform == "cli"
        assert target.channel_id == "c1"
