"""ConfigurationRunner — dispatches to the appropriate pattern implementation."""

from __future__ import annotations

from typing import Any, Callable, Coroutine, Dict, List, Optional

from cuga.backend.multi_agent.agent_bus import AgentBus
from cuga.backend.multi_agent.config import MultiAgentConfig
from cuga.backend.multi_agent.patterns.pipeline import RunResult, run_pipeline
from cuga.backend.multi_agent.patterns.peer_to_peer import run_peer_to_peer
from cuga.backend.multi_agent.patterns.supervisor import run_supervisor
from cuga.backend.multi_agent.patterns.swarm import run_swarm
from cuga.backend.multi_agent.task_state import TaskState
from cuga.backend.skills.loader import discover_skills

SlackPoster = Optional[Callable[[str], Coroutine[Any, Any, None]]]


class ConfigurationRunner:
    def __init__(
        self,
        config: MultiAgentConfig,
        agents: Optional[Dict[str, Any]] = None,
        callbacks: Optional[List[Any]] = None,
    ):
        self._config = config
        self._agents = agents or {}
        self._callbacks = callbacks or []
        self._last_task_state: Optional[TaskState] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        request: str,
        task_id: str,
        slack_poster: SlackPoster = None,
    ) -> RunResult:
        task_state = TaskState(task_id=task_id)
        self._last_task_state = task_state

        try:
            result = await self._dispatch(request, task_id, task_state, slack_poster)
        finally:
            task_state.complete()

        return result

    def build_bus(self) -> AgentBus:
        bus = AgentBus()
        for agent_cfg in self._config.agents:
            peers = agent_cfg.peers if agent_cfg.peers else []
            bus.register(
                agent_cfg.id,
                _make_noop_handler(),
                peers=peers if peers else [],
            )
        return bus

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        request: str,
        task_id: str,
        task_state: TaskState,
        slack_poster: SlackPoster = None,
    ) -> RunResult:
        pattern = self._config.pattern

        if pattern == "supervisor":
            return await run_supervisor(
                config=self._config,
                agents=self._agents,
                request=request,
                task_id=task_id,
                task_state=task_state,
                callbacks=self._callbacks or None,
            )

        if pattern == "swarm":
            return await run_swarm(
                config=self._config,
                agents=self._agents,
                request=request,
                task_id=task_id,
                task_state=task_state,
                slack_poster=slack_poster,
                callbacks=self._callbacks or None,
            )

        if pattern == "peer_to_peer":
            return await run_peer_to_peer(
                config=self._config,
                agents=self._agents,
                request=request,
                task_id=task_id,
                task_state=task_state,
            )

        # pipeline / hybrid
        return await run_pipeline(
            config=self._config,
            agents=self._agents,
            request=request,
            task_id=task_id,
            task_state=task_state,
            discover_skills_fn=discover_skills,
        )


def _make_noop_handler():
    async def _noop(msg):
        return {}
    return _noop
