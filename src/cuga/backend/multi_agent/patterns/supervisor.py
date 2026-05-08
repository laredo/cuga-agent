"""Supervisor pattern: delegates to CugaSupervisor with worker agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from cuga.backend.multi_agent.patterns.pipeline import RunResult

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import MultiAgentConfig
    from cuga.backend.multi_agent.task_state import TaskState

from cuga import CugaSupervisor


async def run_supervisor(
    config: "MultiAgentConfig",
    agents: Optional[Dict[str, Any]],
    request: str,
    task_id: str,
    task_state: "TaskState",
    callbacks: Optional[List[Any]] = None,
) -> RunResult:
    entry_cfg = next(a for a in config.agents if a.role == "entry")
    worker_ids = [a.id for a in config.agents if a.role == "worker"]
    worker_agents: Dict[str, Any] = {}
    for wid in worker_ids:
        if agents and wid in agents:
            worker_agents[wid] = agents[wid]
        else:
            worker_agents[wid] = None

    supervisor = CugaSupervisor(
        agents=worker_agents,
        description=entry_cfg.instructions,
        callbacks=callbacks,
    )
    result = await supervisor.invoke(request, task_id=task_id)
    return RunResult(answer=result.answer, task_id=task_id)
