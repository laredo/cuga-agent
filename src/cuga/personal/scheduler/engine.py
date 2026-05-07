"""SchedulerEngine — cron-based asyncio job runner."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from cuga.personal.gateway.base import MessageEvent, MessageType
from cuga.personal.scheduler.models import JobState, ScheduledJob


class SchedulerEngine:
    """
    Runs scheduled jobs using cron expressions (via croniter).
    Jobs are held in-memory; persistence via storage is wired in later.
    """

    def __init__(self, storage, session_manager, skill_loader, gateway, check_interval: int = 30):
        self._storage = storage
        self._session_manager = session_manager
        self._skill_loader = skill_loader
        self._gateway = gateway
        self._check_interval = check_interval
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    async def create_job(self, job: ScheduledJob) -> ScheduledJob:
        job.next_run = _next_run(job.schedule)
        self._jobs[job.id] = job
        return job

    async def list_jobs(self) -> List[ScheduledJob]:
        return list(self._jobs.values())

    async def pause_job(self, job_id: str) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].state = JobState.PAUSED

    async def resume_job(self, job_id: str) -> None:
        if job_id in self._jobs:
            job = self._jobs[job_id]
            if job.state == JobState.PAUSED:
                job.state = JobState.ACTIVE
                job.next_run = _next_run(job.schedule)

    async def delete_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_job(self, job: ScheduledJob) -> None:
        """Run the skill for this job, deliver the draft, and request approval."""
        try:
            skill = await self._skill_loader.load(job.skill_name)

            event = MessageEvent(
                id=str(uuid.uuid4()),
                channel_id=job.delivery.channel_id,
                user_id=job.user_id,
                platform=job.delivery.platform,
                type=MessageType.TEXT,
                text=job.prompt,
                timestamp=datetime.now(timezone.utc),
            )
            session = await self._session_manager.get_or_create_session(event)
            agent = session.get_agent()
            await self._skill_loader.activate(skill, agent)
            result = await agent.invoke(job.prompt, thread_id=session.thread_id)

            session.active_skill = job.skill_name

            needs_approval = skill.metadata.enterprise.get("approval_required", False)
            if needs_approval:
                session.pending_approval = result.answer
                output = (
                    f"{result.answer}\n\n"
                    f"---\n"
                    f"Reply **approve** to post to #product-updates, or **discard** to cancel."
                )
            else:
                output = result.answer

            await self._gateway.send(target=job.delivery, text=output)

            job.runs_completed += 1
            job.last_run = datetime.now(timezone.utc)

            if job.repeat != -1 and job.runs_completed >= job.repeat:
                job.state = JobState.COMPLETED
            else:
                job.next_run = _next_run(job.schedule)

        except Exception as exc:
            job.state = JobState.FAILED
            job.metadata["last_error"] = str(exc)

    # ------------------------------------------------------------------
    # Internal tick loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            await self.tick()
            await asyncio.sleep(self._check_interval)

    async def tick(self) -> None:
        now = datetime.now(timezone.utc)
        for job in list(self._jobs.values()):
            if job.state != JobState.ACTIVE:
                continue
            if job.next_run and job.next_run <= now:
                asyncio.create_task(self.execute_job(job))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _next_run(cron_expr: str) -> Optional[datetime]:
    """Return the next datetime after now for the given cron expression."""
    try:
        from croniter import croniter

        return croniter(cron_expr, datetime.now(timezone.utc)).get_next(datetime)
    except Exception:
        return None
