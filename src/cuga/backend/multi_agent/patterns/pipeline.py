"""Sequential pipeline pattern: entry → workers → exit."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import AgentConfig, MultiAgentConfig
    from cuga.backend.multi_agent.task_state import TaskState


@dataclass
class RunResult:
    answer: str
    task_id: str


def _build_graph_state(request: str) -> Dict[str, Any]:
    """Build the initial state dict that CugaAgent.graph.ainvoke expects.

    The graph needs chat_messages (LangChain messages), input (str), and url (str).
    task_state is a patterns-layer concern and must NOT be passed to the graph —
    AgentState has no such field and LangGraph would reject or corrupt the state.
    """
    try:
        from langchain_core.messages import HumanMessage
        return {
            "chat_messages": [HumanMessage(content=request)],
            "input": request,
            "url": "",
        }
    except ImportError:
        # Fallback for test environments where langchain_core may not be available
        return {"input": request, "url": ""}


def _extract_answer(result: Any) -> str:
    """Extract answer from graph.ainvoke result.

    graph.ainvoke returns a dict with 'final_answer' for real CugaAgent instances.
    Tests use MagicMock objects with an 'answer' attribute (str).
    We guard with isinstance(…, str) so MagicMock auto-attributes don't shadow the real value.
    """
    if isinstance(result, dict):
        return result.get("final_answer") or result.get("answer") or ""
    for attr in ("final_answer", "answer"):
        val = getattr(result, attr, None)
        if isinstance(val, str):
            return val
    return ""


def _sorted_agents(config: "MultiAgentConfig") -> List["AgentConfig"]:
    """Return agents in pipeline order: entry, then workers following edges, then exit."""
    by_id = {a.id: a for a in config.agents}
    entry = next(a for a in config.agents if a.role == "entry")

    # Build adjacency from edges
    next_of: Dict[str, str] = {e.from_agent: e.to for e in config.edges}

    ordered = [entry]
    current = entry.id
    visited = {current}
    while current in next_of:
        nxt = next_of[current]
        if nxt in visited:
            break
        ordered.append(by_id[nxt])
        visited.add(nxt)
        current = nxt

    return ordered


async def run_pipeline(
    config: "MultiAgentConfig",
    agents: Dict[str, Any],
    request: str,
    task_id: str,
    task_state: "TaskState",
    discover_skills_fn: Optional[Any] = None,
) -> RunResult:
    ordered = _sorted_agents(config)
    accumulated = request
    last_answer = ""

    for agent_cfg in ordered:
        agent = agents.get(agent_cfg.id)
        if agent is None:
            raise KeyError(f"Agent {agent_cfg.id!r} not provided")

        # Optionally load skills for this agent
        if discover_skills_fn is not None and agent_cfg.skills and agent_cfg.skills.enabled:
            discover_skills_fn(agent_cfg.skills.paths or None)

        state_input = _build_graph_state(accumulated)

        result = await asyncio.wait_for(
            agent.graph.ainvoke(
                state_input,
                config={"configurable": {"thread_id": f"{task_id}-{agent_cfg.id}"}},
            ),
            timeout=agent_cfg.timeout_seconds,
        )

        last_answer = _extract_answer(result)
        accumulated = f"{accumulated}\n\n{last_answer}"

    return RunResult(answer=last_answer, task_id=task_id)
