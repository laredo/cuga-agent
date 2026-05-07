"""Peer-to-peer pattern: entry runs first, peers may exchange, exit produces final answer."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict

from cuga.backend.multi_agent.patterns.pipeline import RunResult, _extract_answer, _build_graph_state

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import MultiAgentConfig
    from cuga.backend.multi_agent.task_state import TaskState


async def run_peer_to_peer(
    config: "MultiAgentConfig",
    agents: Dict[str, Any],
    request: str,
    task_id: str,
    task_state: "TaskState",
) -> RunResult:
    entry = next(a for a in config.agents if a.role == "entry")
    exit_agent = next(a for a in config.agents if a.role == "exit")

    entry_result = await asyncio.wait_for(
        agents[entry.id].graph.ainvoke(
            _build_graph_state(request),
            config={"configurable": {"thread_id": f"{task_id}-{entry.id}"}},
        ),
        timeout=entry.timeout_seconds,
    )

    accumulated = f"{request}\n\n{_extract_answer(entry_result)}"

    exit_result = await asyncio.wait_for(
        agents[exit_agent.id].graph.ainvoke(
            _build_graph_state(accumulated),
            config={"configurable": {"thread_id": f"{task_id}-{exit_agent.id}"}},
        ),
        timeout=exit_agent.timeout_seconds,
    )

    return RunResult(answer=_extract_answer(exit_result), task_id=task_id)
