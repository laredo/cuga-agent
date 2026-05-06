"""PersonalAgentOrchestrator — wires gateway, skills, scheduler, and agent together."""
from typing import Optional

from cuga.personal.gateway.base import DeliveryTarget, MessageEvent
from cuga.personal.gateway.session import SessionManager
from cuga.personal.skills.dispatcher import SkillDispatcher
from cuga.personal.skills.loader import SkillLoader
from cuga.personal.scheduler.engine import SchedulerEngine


class PersonalAgentOrchestrator:
    """
    Main orchestration loop.

    Flow: inbound MessageEvent → session → skill dispatch → agent invoke → deliver reply.
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
        self._skill_dispatcher._skills = [
            await self._skill_loader.load(s.name) for s in skills
        ]
        if self._scheduler:
            await self._scheduler.start()
        await self._gateway.start(on_message=self.handle_message)

    async def handle_message(self, event: MessageEvent) -> None:
        """
        1. Get/create session for user
        2. Dispatch to skill (or fall back to general agent)
        3. Activate skill if matched
        4. Invoke agent
        5. Deliver response
        """
        session = await self._session_manager.get_or_create_session(event)
        skill = await self._skill_dispatcher.dispatch(event)
        agent = session.get_agent()

        if skill:
            await self._skill_loader.activate(skill, agent)

        result = await agent.invoke(event.text, thread_id=session.thread_id)

        target = DeliveryTarget(
            platform=event.platform,
            channel_id=event.channel_id,
            thread_id=event.thread_id,
        )
        await self._gateway.send(target, result.answer)
