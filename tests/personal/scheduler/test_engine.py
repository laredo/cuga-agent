"""Tests for SchedulerEngine — job creation, tick logic, execution."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from cuga.personal.gateway.base import DeliveryTarget
from cuga.personal.scheduler.engine import SchedulerEngine
from cuga.personal.scheduler.models import JobState, ScheduledJob


def _make_job(schedule="* * * * *", repeat=-1, skill_name="test-skill"):
    return ScheduledJob(
        id="job-1",
        name="Test Job",
        schedule=schedule,
        skill_name=skill_name,
        prompt="run the skill",
        user_id="user-1",
        delivery=DeliveryTarget(platform="cli", channel_id="s1"),
        created_at=datetime.now(timezone.utc),
        repeat=repeat,
    )


@pytest.fixture
def engine():
    mock_storage = MagicMock()
    mock_session_manager = MagicMock()
    mock_skill_loader = MagicMock()
    mock_gateway = AsyncMock()
    return SchedulerEngine(
        storage=mock_storage,
        session_manager=mock_session_manager,
        skill_loader=mock_skill_loader,
        gateway=mock_gateway,
    )


class TestSchedulerEngine:
    @pytest.mark.asyncio
    async def test_create_job(self, engine):
        job = _make_job()
        created = await engine.create_job(job)
        assert created.id == "job-1"
        assert created.state == JobState.ACTIVE

    @pytest.mark.asyncio
    async def test_create_job_calculates_next_run(self, engine):
        job = _make_job(schedule="0 16 * * 5")
        created = await engine.create_job(job)
        assert created.next_run is not None

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, engine):
        jobs = await engine.list_jobs()
        assert jobs == []

    @pytest.mark.asyncio
    async def test_list_jobs_after_create(self, engine):
        await engine.create_job(_make_job())
        jobs = await engine.list_jobs()
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_pause_job(self, engine):
        job = await engine.create_job(_make_job())
        await engine.pause_job(job.id)
        jobs = await engine.list_jobs()
        assert jobs[0].state == JobState.PAUSED

    @pytest.mark.asyncio
    async def test_execute_job_invokes_skill(self, engine):
        mock_skill = MagicMock()
        mock_skill.metadata.name = "test-skill"
        engine._skill_loader.scan = AsyncMock(return_value=[])
        engine._skill_loader.load = AsyncMock(return_value=mock_skill)
        engine._skill_loader.activate = AsyncMock()

        mock_session = MagicMock()
        mock_session.thread_id = "t-123"
        mock_agent = AsyncMock()
        mock_agent.invoke = AsyncMock(return_value=MagicMock(answer="done!"))
        mock_session.get_agent = MagicMock(return_value=mock_agent)
        engine._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        job = await engine.create_job(_make_job())
        await engine.execute_job(job)

        mock_agent.invoke.assert_called_once()
        engine._gateway.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_job_updates_run_count(self, engine):
        mock_skill = MagicMock()
        engine._skill_loader.load = AsyncMock(return_value=mock_skill)
        engine._skill_loader.activate = AsyncMock()

        mock_session = MagicMock()
        mock_session.thread_id = "t-123"
        mock_agent = AsyncMock()
        mock_agent.invoke = AsyncMock(return_value=MagicMock(answer="done"))
        mock_session.get_agent = MagicMock(return_value=mock_agent)
        engine._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        job = await engine.create_job(_make_job())
        await engine.execute_job(job)
        assert job.runs_completed == 1
        assert job.last_run is not None

    @pytest.mark.asyncio
    async def test_finite_job_completes_after_n_runs(self, engine):
        mock_skill = MagicMock()
        engine._skill_loader.load = AsyncMock(return_value=mock_skill)
        engine._skill_loader.activate = AsyncMock()

        mock_session = MagicMock()
        mock_session.thread_id = "t-1"
        mock_agent = AsyncMock()
        mock_agent.invoke = AsyncMock(return_value=MagicMock(answer="ok"))
        mock_session.get_agent = MagicMock(return_value=mock_agent)
        engine._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        job = await engine.create_job(_make_job(repeat=1))
        await engine.execute_job(job)
        assert job.state == JobState.COMPLETED
