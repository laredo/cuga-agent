"""Swarm pattern: event-queue-driven agent dispatch with one task per message.

How it works
------------
``SwarmAgentFactory`` (see swarm_factory.py) gives each agent:
  • An ``EventQueue`` inbox (branch event infrastructure).
  • A ``dispatch_to_<peer_id>`` LangChain tool for every declared peer.

When an agent calls ``dispatch_to_fact_checker(content="...")`` **during its
LangGraph ReAct loop**, that tool immediately enqueues an ``Event(type=AGENT)``
into fact_checker's EventQueue.  ``run_swarm`` runs a drain task per queue;
every AGENT event spawns a fresh ``asyncio.Task`` — so five documents found by
web_searcher become five concurrent fact_checker tasks, each starting the
moment web_searcher dispatches that document.

NOTIFY_SLACK: text directive (in agent output)
----------------------------------------------
Agents can still post to Slack by including ``NOTIFY_SLACK:<text>`` lines in
their final text output.  These are parsed after ``graph.ainvoke()`` returns
and posted via the ``slack_poster`` coroutine.

DISPATCH: text directive — REMOVED
-----------------------------------
Text-based DISPATCH blocks are no longer used for worker→worker routing.
All routing is done through tool calls so dispatch happens mid-run.
The entry agent's plain-text output (non-NOTIFY lines) becomes the Slack ack.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, List, Optional, Tuple

from loguru import logger

from cuga.backend.events.models import Event, EventType
from cuga.backend.events.queue import EventQueue
from cuga.backend.multi_agent.patterns.pipeline import (
    RunResult,
    _build_graph_state,
    _extract_answer,
)

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import MultiAgentConfig
    from cuga.backend.multi_agent.task_state import TaskState

SlackPoster = Callable[[str], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Output parsing — NOTIFY_SLACK: only
# ---------------------------------------------------------------------------

def _parse_slack_notifications(raw: str) -> Tuple[str, List[str]]:
    """Extract NOTIFY_SLACK: blocks and leftover plain text from agent output.

    Returns ``(leftover, notify_texts)`` where:
      * ``leftover``     — lines outside any NOTIFY_SLACK: block; used as the
                           entry agent's immediate Slack acknowledgement text.
      * ``notify_texts`` — list of texts to post to the Slack thread.
    """
    leftover_lines: List[str] = []
    notify_texts: List[str] = []
    in_notify = False
    current_lines: List[str] = []

    def _flush_notify() -> None:
        text = "\n".join(current_lines).strip()
        if text:
            notify_texts.append(text)

    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("NOTIFY_SLACK:"):
            if in_notify:
                _flush_notify()
            in_notify = True
            current_lines = []
            inline = stripped[len("NOTIFY_SLACK:"):].strip()
            if inline:
                current_lines = [inline]
        elif in_notify:
            current_lines.append(line)
        else:
            leftover_lines.append(line)

    if in_notify:
        _flush_notify()

    leftover = "\n".join(leftover_lines).strip()
    # Strip markdown code fences from the entry-agent ack — raw Python code
    # must never be posted to Slack.  This happens when CugaLite's router
    # returns the last model-generated code block as the "final answer".
    leftover = re.sub(r"```[^\n]*\n.*?```", "", leftover, flags=re.DOTALL).strip()
    return leftover, notify_texts


# ---------------------------------------------------------------------------
# Single-message agent task
# ---------------------------------------------------------------------------

async def _agent_task(
    agent_id: str,
    agent: Any,
    content: str,
    task_id: str,
    msg_index: int,
    timeout: int,
    is_entry: bool,
    first_response_queue: Optional["asyncio.Queue[str]"],
    slack_poster: Optional[SlackPoster],
    callbacks: Optional[List[Any]] = None,
) -> None:
    """Invoke one agent on one message, parse NOTIFY_SLACK: and post updates."""
    # Bind agent name to every log line for this task (ainvoke AND post-processing)
    # so the dashboard's per-agent raw-log filter works across the full execution.
    with logger.contextualize(agent=agent_id):
        logger.info(f"[swarm:{agent_id}#{msg_index}] processing ({len(content)} chars)")

        invoke_config: Dict[str, Any] = {
            "configurable": {"thread_id": f"{task_id}-{agent_id}-{msg_index}"},
            "tags": [agent_id],
        }
        if callbacks:
            invoke_config["callbacks"] = callbacks

        # --- FIX: Inject knowledge engine configuration if available ---
        if hasattr(agent, "_inject_knowledge_to_config"):
            agent._inject_knowledge_to_config(invoke_config)

        try:
            result = await asyncio.wait_for(
                agent.graph.ainvoke(_build_graph_state(content), config=invoke_config),
                timeout=float(timeout),
            )
        except asyncio.TimeoutError:
            logger.warning(f"[swarm:{agent_id}#{msg_index}] timed out after {timeout}s")
            if is_entry and first_response_queue is not None:
                await first_response_queue.put("⏳ Request received — working in the background.")
            return
        except Exception as exc:
            logger.error(f"[swarm:{agent_id}#{msg_index}] error: {exc}")
            if is_entry and first_response_queue is not None:
                await first_response_queue.put(f"❌ Error during swarm execution: {exc}")
            return

        answer = _extract_answer(result)
        leftover, notify_texts = _parse_slack_notifications(answer)

        if slack_poster:
            for text in notify_texts:
                asyncio.create_task(_safe_post(slack_poster, text, agent_id))

        if is_entry and first_response_queue is not None:
            await first_response_queue.put(leftover or "_Working on it…_")
            logger.info(f"[swarm:{agent_id}#{msg_index}] ack posted to Slack")


async def _safe_post(poster: SlackPoster, text: str, agent_id: str) -> None:
    try:
        await poster(text)
    except Exception as exc:
        logger.warning(f"[swarm:{agent_id}] slack_poster error: {exc}")


# ---------------------------------------------------------------------------
# run_swarm
# ---------------------------------------------------------------------------

_task_posters: Dict[str, SlackPoster] = {}
_task_first_response_queues: Dict[str, asyncio.Queue] = {}
_agent_counter: int = 0

def _global_spawn(agent_id: str, content: str, task_id: str, agents: Dict[str, Any], timeout_map: Dict[str, int], entry_id: str, callbacks: List[Any]) -> None:
    global _agent_counter
    _agent_counter += 1
    idx = _agent_counter
    
    poster = _task_posters.get(task_id)
    first_resp_q = _task_first_response_queues.get(task_id) if agent_id == entry_id else None
    
    asyncio.create_task(
        _agent_task(
            agent_id=agent_id,
            agent=agents[agent_id],
            content=content,
            task_id=task_id,
            msg_index=idx,
            timeout=timeout_map.get(agent_id, 300),
            is_entry=(agent_id == entry_id),
            first_response_queue=first_resp_q,
            slack_poster=poster,
            callbacks=callbacks,
        ),
        name=f"swarm-{task_id}-{agent_id}-{idx}",
    )
    logger.debug(f"[run_swarm] spawned {agent_id!r} task #{idx}")


async def run_swarm(
    config: "MultiAgentConfig",
    agents: Dict[str, Any],
    request: str,
    task_id: str,
    task_state: "TaskState",
    agent_queues: Optional[Dict[str, EventQueue]] = None,
    slack_poster: Optional[SlackPoster] = None,
    callbacks: Optional[List[Any]] = None,
) -> RunResult:
    """Start per-agent EventQueue drain loops and seed the entry agent.

    Each ``Event(type=AGENT)`` arriving in an agent's queue spawns a fresh
    ``asyncio.Task``.  Returns as soon as the entry agent posts its ack; all
    worker tasks continue concurrently in the background.

    Requires ``agent_queues`` from ``SwarmAgentFactory``.
    """
    if not agent_queues:
        raise ValueError(
            "run_swarm requires agent_queues from SwarmAgentFactory. "
            "Use SwarmAgentFactory instead of AgentFactory for swarm topologies."
        )

    entry_id = next(a.id for a in config.agents if a.role == "entry")
    timeout_map = {a.id: a.timeout_seconds for a in config.agents}
    first_response_queue: asyncio.Queue[str] = asyncio.Queue()
    
    # Register global state for this task
    if slack_poster:
        _task_posters[task_id] = slack_poster
    _task_first_response_queues[task_id] = first_response_queue

    # Ensure drain loops are started ONLY ONCE per agent
    for agent_cfg in config.agents:
        queue = agent_queues[agent_cfg.id]
        if not getattr(queue, "_processor_task", None):
            # Capture agent_id in a closure default arg
            async def _handle(event: Event, _agent_id=agent_cfg.id) -> None:
                if event.type == EventType.AGENT:
                    content = event.payload.get("content", "")
                    evt_task_id = event.payload.get("task_id", "")
                    _global_spawn(_agent_id, content, evt_task_id, agents, timeout_map, entry_id, callbacks or [])

            try:
                # Force restart the processor to apply any code changes (like task_id support)
                if queue._running:
                    await queue.stop()
                queue.start_processor(_handle)
                logger.info(f"[run_swarm] EventQueue drain started/restarted for {agent_cfg.id!r}")
            except Exception:
                logger.debug(f"[run_swarm] Event processor already running for {agent_cfg.id!r}")

    # Seed the entry agent with the initial user request
    from cuga.backend.events.models import EventSource
    seed_event = Event(
        type=EventType.AGENT,
        source=EventSource.INTERNAL,
        event_name="agent_dispatch",
        payload={
            "sender": "__system__",
            "recipient": entry_id,
            "content": request,
            "task_id": task_id,
        },
    )
    await agent_queues[entry_id].enqueue(seed_event)
    logger.info(f"[run_swarm] seeded {entry_id!r} with request ({len(request)} chars)")

    # Wait for the entry agent's immediate ack, then return
    entry_timeout = float(timeout_map[entry_id])
    ack_wait = entry_timeout + 30.0   # generous buffer beyond agent's own timeout
    try:
        ack = await asyncio.wait_for(first_response_queue.get(), timeout=ack_wait)
    except asyncio.TimeoutError:
        logger.error(
            f"[run_swarm] entry agent did not respond within {ack_wait:.0f}s for {task_id!r}"
        )
        ack = "⏳ Request queued — I'll post updates here as the team works on it."

    return RunResult(answer=ack, task_id=task_id)
