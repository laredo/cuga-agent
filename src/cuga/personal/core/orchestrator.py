"""PersonalAgentOrchestrator — wires gateway, skills, scheduler, and agent together."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from cuga.personal.gateway.base import DeliveryTarget, MessageEvent
from cuga.personal.gateway.session import Session, SessionManager
from cuga.personal.skills.dispatcher import SkillDispatcher
from cuga.personal.skills.loader import SkillLoader
from cuga.personal.scheduler.engine import SchedulerEngine
from cuga.personal.scheduler.models import ScheduledJob

_APPROVE_WORDS = {"approve", "yes", "post it", "post", "send it", "looks good", "lgtm", "ok", "okay"}
_DISCARD_WORDS = {"discard", "no", "cancel", "skip", "don't post", "nevermind", "never mind", "abort"}


class PersonalAgentOrchestrator:
    """
    Main orchestration loop.

    Flow per message:
      1. Scheduling intent check  → register job and confirm
      2. Run-now command          → trigger a job immediately
      3. Pending approval check   → handle approve/discard
      4. Normal dispatch          → session → skill → agent → reply
    """

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        skill_loader: SkillLoader,
        skill_dispatcher: SkillDispatcher,
        gateway,
        scheduler: Optional[SchedulerEngine] = None,
    ):
        self._session_manager = session_manager
        self._skill_loader = skill_loader
        self._skill_dispatcher = skill_dispatcher
        self._gateway = gateway
        self._scheduler = scheduler

    async def start(self) -> None:
        """Start all components."""
        skills = await self._skill_loader.scan()
        self._skill_dispatcher._skills = [await self._skill_loader.load(s.name) for s in skills]
        if getattr(self, "_scheduler", None):
            await self._scheduler.start()
        await self._gateway.start(on_message=self.handle_message)

    async def handle_message(self, event: MessageEvent) -> None:
        target = DeliveryTarget(
            platform=event.platform,
            channel_id=event.channel_id,
            thread_id=event.thread_id,
        )

        # 1. Scheduling intent
        if getattr(self, "_scheduler", None):
            job = await self._try_create_schedule(event)
            if job is not None:
                await self._gateway.send(target, _schedule_confirmation(job))
                return

        # 2. /run <skill> — immediate job trigger for testing
        if getattr(self, "_scheduler", None) and event.text.lower().startswith("/run"):
            handled = await self._handle_run_now(event, target)
            if handled:
                return

        # 3. Pending approval
        session = await self._session_manager.get_or_create_session(event)
        if session.pending_approval is not None:
            handled = await self._handle_approval(session, event, target)
            if handled:
                return

        # 4. Normal dispatch
        skill = await self._skill_dispatcher.dispatch(event)

        # Re-activate last skill for follow-up messages (e.g. "approve", edits)
        if skill is None and isinstance(getattr(session, "active_skill", None), str):
            try:
                skill = await self._skill_loader.load(session.active_skill)
            except (KeyError, Exception):
                pass

        agent = session.get_agent()
        if skill:
            session.active_skill = skill.metadata.name
            await self._skill_loader.activate(skill, agent)

        result = await agent.invoke(event.text, thread_id=session.thread_id)

        # Check if the agent produced a bulletin draft that needs approval
        if skill and skill.metadata.name == "bulletin" and _looks_like_draft(result.answer):
            session.pending_approval = result.answer

        await self._gateway.send(target, result.answer)

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------

    async def _handle_approval(self, session: Session, event: MessageEvent, target: DeliveryTarget) -> bool:
        """Return True if the message was an approval/discard action."""
        word = event.text.strip().lower().rstrip("!.")
        if word in _APPROVE_WORDS:
            session.pending_approval = None
            session.active_skill = None
            await self._gateway.send(
                target, "Posted to #product-updates ✓\n\nYour bulletin has been shared with the team."
            )
            return True
        if word in _DISCARD_WORDS:
            session.pending_approval = None
            session.active_skill = None
            await self._gateway.send(target, "Discarded. Nothing was posted.")
            return True
        return False

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    async def _try_create_schedule(self, event: MessageEvent) -> Optional[ScheduledJob]:
        from cuga.personal.scheduler.nl_parser import is_schedule_request, parse_schedule

        if not is_schedule_request(event.text):
            return None
        parsed = parse_schedule(event.text)
        if not parsed:
            return None

        job = ScheduledJob(
            id=str(uuid.uuid4()),
            name=parsed["name"],
            schedule=parsed["cron"],
            skill_name=parsed["skill_name"],
            prompt=parsed["prompt"],
            user_id=event.user_id,
            delivery=DeliveryTarget(
                platform=event.platform,
                channel_id=event.channel_id,
            ),
            created_at=datetime.now(timezone.utc),
        )
        return await self._scheduler.create_job(job)

    # ------------------------------------------------------------------
    # /run <skill> — immediate trigger for demo
    # ------------------------------------------------------------------

    async def _handle_run_now(self, event: MessageEvent, target: DeliveryTarget) -> bool:
        """Trigger the most recent job for a skill immediately. Returns True if handled."""
        parts = event.text.strip().split()
        skill_name = parts[1].lower() if len(parts) > 1 else "bulletin"

        jobs = await self._scheduler.list_jobs()
        matching = [j for j in jobs if j.skill_name == skill_name]
        if not matching:
            await self._gateway.send(
                target,
                f"No scheduled jobs found for skill '{skill_name}'. "
                f"Schedule one first, e.g. 'Every Friday at 4pm, send me the {skill_name}.'",
            )
            return True

        job = matching[-1]  # most recently registered
        await self._gateway.send(target, f"Triggering *{job.name}* now…")
        await self._scheduler.execute_job(job)
        return True


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _schedule_confirmation(job: ScheduledJob) -> str:
    next_run = (
        job.next_run.strftime("%A %b %-d at %-I:%M %p UTC") if job.next_run else "the next scheduled time"
    )
    human = job.name.split(job.skill_name + "-", 1)[-1].replace("-", " ")
    return (
        f"Done! Scheduled *{job.skill_name}* to run {human}.\n"
        f"Cron: `{job.schedule}` — next run: *{next_run}*\n"
        f"I'll send the result here for your approval before posting anywhere.\n\n"
        f"To trigger immediately: `/run {job.skill_name}`"
    )


def _looks_like_draft(text: str) -> bool:
    """Heuristic: did the agent produce a bulletin draft?"""
    indicators = ["CUGA Product Update", "What's next:", "— The CUGA Team", "📬"]
    return any(ind in text for ind in indicators)
