"""Tests for SkillDispatcher — command, keyword, and NL matching."""
import pytest

from cuga.personal.gateway.base import MessageEvent, MessageType
from cuga.personal.skills.dispatcher import SkillDispatcher
from cuga.personal.skills.models import LoadedSkill, SkillMetadata
from datetime import datetime, timezone


def _event(text, msg_type=MessageType.TEXT):
    return MessageEvent(
        id="e1", channel_id="c1", user_id="u1", platform="cli",
        type=msg_type, text=text, timestamp=datetime.now(timezone.utc),
    )


def _make_skill(name, commands=None, triggers=None):
    meta = SkillMetadata(
        name=name,
        description=f"Skill {name}",
        commands=commands or [],
        triggers=triggers or [],
    )
    return LoadedSkill(metadata=meta, path=f"/skills/{name}")


class TestSkillDispatcher:
    @pytest.fixture
    def timesheet_skill(self):
        return _make_skill(
            "fill-timesheet",
            commands=["/timesheet"],
            triggers=[
                {"type": "keyword", "value": ["timesheet", "time sheet", "fill time"], "operator": "or"},
            ],
        )

    @pytest.fixture
    def expense_skill(self):
        return _make_skill(
            "expense-report",
            commands=["/expense", "/expenses"],
            triggers=[
                {"type": "keyword", "value": ["expense", "receipt", "reimbursement"], "operator": "or"},
            ],
        )

    @pytest.fixture
    def dispatcher(self, timesheet_skill, expense_skill):
        return SkillDispatcher(skills=[timesheet_skill, expense_skill])

    @pytest.mark.asyncio
    async def test_slash_command_exact_match(self, dispatcher):
        event = _event("/timesheet", MessageType.COMMAND)
        skill = await dispatcher.dispatch(event)
        assert skill is not None
        assert skill.metadata.name == "fill-timesheet"

    @pytest.mark.asyncio
    async def test_slash_command_second_skill(self, dispatcher):
        event = _event("/expense", MessageType.COMMAND)
        skill = await dispatcher.dispatch(event)
        assert skill is not None
        assert skill.metadata.name == "expense-report"

    @pytest.mark.asyncio
    async def test_keyword_trigger_match(self, dispatcher):
        event = _event("can you fill my timesheet please")
        skill = await dispatcher.dispatch(event)
        assert skill is not None
        assert skill.metadata.name == "fill-timesheet"

    @pytest.mark.asyncio
    async def test_keyword_trigger_partial_match(self, dispatcher):
        event = _event("I need to submit an expense report")
        skill = await dispatcher.dispatch(event)
        assert skill is not None
        assert skill.metadata.name == "expense-report"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self, dispatcher):
        event = _event("what is the weather today")
        skill = await dispatcher.dispatch(event)
        assert skill is None

    @pytest.mark.asyncio
    async def test_unknown_command_returns_none(self, dispatcher):
        event = _event("/unknown", MessageType.COMMAND)
        skill = await dispatcher.dispatch(event)
        assert skill is None

    @pytest.mark.asyncio
    async def test_empty_skills_list(self):
        dispatcher = SkillDispatcher(skills=[])
        event = _event("/timesheet", MessageType.COMMAND)
        assert await dispatcher.dispatch(event) is None
