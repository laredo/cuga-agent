"""Tests for ScheduledJob model."""
from datetime import datetime, timezone

from cuga.personal.gateway.base import DeliveryTarget
from cuga.personal.scheduler.models import JobState, ScheduledJob


def _job(**kwargs):
    defaults = dict(
        id="job-1",
        name="Weekly Timesheet",
        schedule="0 16 * * 5",
        skill_name="fill-timesheet",
        prompt="Fill my timesheet for this week",
        user_id="user-1",
        delivery=DeliveryTarget(platform="cli", channel_id="session-1"),
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return ScheduledJob(**defaults)


class TestJobState:
    def test_values(self):
        assert JobState.ACTIVE == "active"
        assert JobState.PAUSED == "paused"
        assert JobState.COMPLETED == "completed"
        assert JobState.FAILED == "failed"


class TestScheduledJob:
    def test_minimal_creation(self):
        job = _job()
        assert job.id == "job-1"
        assert job.state == JobState.ACTIVE
        assert job.repeat == -1
        assert job.runs_completed == 0
        assert job.last_run is None
        assert job.next_run is None
        assert job.metadata == {}

    def test_finite_repeat(self):
        job = _job(repeat=3)
        assert job.repeat == 3

    def test_serialization_roundtrip(self):
        job = _job()
        data = job.model_dump()
        restored = ScheduledJob.model_validate(data)
        assert restored.id == job.id
        assert restored.schedule == job.schedule
        assert restored.delivery.platform == "cli"

    def test_state_transitions(self):
        job = _job()
        assert job.state == JobState.ACTIVE
        job.state = JobState.PAUSED
        assert job.state == JobState.PAUSED
        job.state = JobState.COMPLETED
        assert job.state == JobState.COMPLETED
