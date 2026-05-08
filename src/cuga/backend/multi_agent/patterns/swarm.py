"""Swarm pattern: concurrent agent tasks with asyncio.Queue inboxes and peer ACL.

Routing directives agents embed in their plain-text output:

    DISPATCH:<agent_id>
    <content to route to that agent's inbox>

    NOTIFY_SLACK:<text to post to the Slack thread>

ACL enforced by SwarmBus (from topology ``peers`` fields):
  • sender may route to agents listed in its own ``peers``
  • ALL agents may additionally route to the entry agent
  • ``__system__`` is exempt — seeds the entry agent's inbox

Lifecycle — lazy task spawning
------------------------------
Only the entry agent task is started up front.  Worker tasks are spawned
on-demand the first time a DISPATCH message is routed to them.  This ensures
workers are always alive when their first message arrives, regardless of how
long upstream agents spend doing tool calls.  Workers exit after a short idle
window once their queue drains.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, List, Optional, Tuple

from loguru import logger

from cuga.backend.multi_agent.patterns.pipeline import (
    RunResult,
    _build_graph_state,
    _extract_answer,
)

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import AgentConfig, MultiAgentConfig
    from cuga.backend.multi_agent.task_state import TaskState

SlackPoster = Callable[[str], Coroutine[Any, Any, None]]
EnsureTask = Callable[[str], None]


# ---------------------------------------------------------------------------
# Message envelope
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SwarmMessage:
    sender: str
    content: str


_SHUTDOWN = SwarmMessage(sender="__shutdown__", content="")

_WORKER_IDLE_TIMEOUT = 60.0   # seconds a worker waits for another message before exiting


# ---------------------------------------------------------------------------
# SwarmBus
# ---------------------------------------------------------------------------

class SwarmBus:
    """Per-agent asyncio.Queue inboxes with peer ACL enforcement.

    ACL rules:
      * sender → recipient  allowed when  ``recipient in sender.peers``
      * any agent           → entry agent always allowed
      * ``__system__``      → entry agent (bootstrap only)
    """

    def __init__(self, agent_configs: List["AgentConfig"]) -> None:
        self._queues: Dict[str, asyncio.Queue[SwarmMessage]] = {
            a.id: asyncio.Queue() for a in agent_configs
        }
        self._peers: Dict[str, frozenset[str]] = {
            a.id: frozenset(a.peers) for a in agent_configs
        }
        self._entry_id: str = next(a.id for a in agent_configs if a.role == "entry")

    @property
    def entry_id(self) -> str:
        return self._entry_id

    def send(self, sender: str, recipient: str, content: str) -> None:
        """Put *content* in *recipient*'s inbox; raise on ACL violation or unknown agent."""
        if recipient not in self._queues:
            raise ValueError(f"Unknown agent: {recipient!r}")
        if sender != "__system__" and recipient != self._entry_id:
            allowed = self._peers.get(sender, frozenset())
            if recipient not in allowed:
                raise PermissionError(
                    f"ACL violation: {sender!r} → {recipient!r}. "
                    f"Declared peers of {sender!r}: {sorted(allowed)}"
                )
        self._queues[recipient].put_nowait(SwarmMessage(sender=sender, content=content))
        logger.debug(f"[SwarmBus] {sender!r} → {recipient!r} ({len(content)} chars)")

    async def receive(self, agent_id: str, timeout: float) -> Optional[SwarmMessage]:
        """Return next message or None after *timeout* seconds of silence."""
        try:
            return await asyncio.wait_for(self._queues[agent_id].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def _parse_output(raw: str) -> Tuple[str, List[str], List[Tuple[str, str]]]:
    """Parse agent output for routing and Slack notification directives.

    Returns ``(leftover, notify_texts, dispatches)`` where:

    * ``leftover``      — plain text outside any directive block; used as the
                          entry agent's immediate Slack acknowledgement
    * ``notify_texts``  — list of ``NOTIFY_SLACK:`` payloads to post to Slack
    * ``dispatches``    — list of ``(recipient, content)`` from ``DISPATCH:`` blocks
    """
    leftover_lines: List[str] = []
    notify_texts: List[str] = []
    dispatches: List[Tuple[str, str]] = []

    current_directive: Optional[str] = None   # "DISPATCH" | "NOTIFY_SLACK"
    current_recipient: Optional[str] = None
    current_lines: List[str] = []

    def _flush() -> None:
        if current_directive == "DISPATCH" and current_recipient:
            dispatches.append((current_recipient, "\n".join(current_lines).strip()))
        elif current_directive == "NOTIFY_SLACK":
            text = "\n".join(current_lines).strip()
            if text:
                notify_texts.append(text)

    for line in raw.splitlines():
        stripped = line.strip()
        upper = stripped.upper()

        if upper.startswith("DISPATCH:"):
            _flush()
            current_directive = "DISPATCH"
            current_recipient = stripped[len("DISPATCH:"):].strip()
            current_lines = []
        elif upper.startswith("NOTIFY_SLACK:"):
            _flush()
            current_directive = "NOTIFY_SLACK"
            current_recipient = None
            inline = stripped[len("NOTIFY_SLACK:"):].strip()
            current_lines = [inline] if inline else []
        elif current_directive is not None:
            current_lines.append(line)
        else:
            leftover_lines.append(line)

    _flush()
    return "\n".join(leftover_lines).strip(), notify_texts, dispatches


# ---------------------------------------------------------------------------
# Agent task
# ---------------------------------------------------------------------------

async def _agent_task(
    agent_id: str,
    agent: Any,
    bus: SwarmBus,
    task_id: str,
    timeout: int,
    is_entry: bool,
    first_response_queue: "asyncio.Queue[str]",
    slack_poster: Optional[SlackPoster],
    ensure_task: EnsureTask,
) -> None:
    """Dequeue → invoke LLM → parse directives → spawn workers + route + post Slack."""
    first_response_sent = False
    idle_timeout = 5.0 if is_entry else _WORKER_IDLE_TIMEOUT

    while True:
        msg = await bus.receive(agent_id, timeout=idle_timeout)

        if msg is None:
            logger.debug(f"[swarm:{agent_id}] idle {idle_timeout}s — task exiting")
            return
        if msg is _SHUTDOWN:
            return

        logger.info(f"[swarm:{agent_id}] ← {msg.sender!r} ({len(msg.content)} chars)")

        try:
            result = await asyncio.wait_for(
                agent.graph.ainvoke(
                    _build_graph_state(msg.content),
                    config={"configurable": {"thread_id": f"{task_id}-{agent_id}"}},
                ),
                timeout=float(timeout),
            )
        except asyncio.TimeoutError:
            logger.warning(f"[swarm:{agent_id}] LLM timed out after {timeout}s")
            if is_entry and not first_response_sent:
                await first_response_queue.put("⏳ Request received — working in the background.")
                first_response_sent = True
            continue
        except Exception as exc:
            logger.error(f"[swarm:{agent_id}] error: {exc}")
            if is_entry and not first_response_sent:
                await first_response_queue.put(f"❌ Error: {exc}")
                first_response_sent = True
            continue

        answer = _extract_answer(result)
        leftover, notify_texts, dispatches = _parse_output(answer)

        # Post NOTIFY_SLACK: updates to the Slack thread
        if slack_poster:
            for text in notify_texts:
                asyncio.create_task(_safe_post(slack_poster, text, agent_id))

        # Spawn worker tasks on-demand, then route DISPATCH: messages
        for recipient, content in dispatches:
            try:
                ensure_task(recipient)        # spawn if not already running
                bus.send(agent_id, recipient, content)
            except (PermissionError, ValueError) as exc:
                logger.warning(f"[swarm:{agent_id}] routing skipped: {exc}")

        # Entry agent: signal first response then exit — workers handle the rest
        if is_entry and not first_response_sent:
            await first_response_queue.put(leftover or "_Working on it…_")
            first_response_sent = True
            logger.debug(f"[swarm:{agent_id}] ack sent, task exiting")
            return


async def _safe_post(poster: SlackPoster, text: str, agent_id: str) -> None:
    try:
        await poster(text)
    except Exception as exc:
        logger.warning(f"[swarm:{agent_id}] slack_poster error: {exc}")


# ---------------------------------------------------------------------------
# run_swarm
# ---------------------------------------------------------------------------

async def run_swarm(
    config: "MultiAgentConfig",
    agents: Dict[str, Any],
    request: str,
    task_id: str,
    task_state: "TaskState",
    slack_poster: Optional[SlackPoster] = None,
    callbacks: Optional[List[Any]] = None,
) -> RunResult:
    """Seed the entry agent and return its immediate ack; workers spawn on-demand.

    Only the entry task is started up front.  Worker tasks are created the
    moment a DISPATCH message is routed to them, so they are guaranteed to be
    alive when the message arrives regardless of upstream processing time.
    """
    bus = SwarmBus(config.agents)
    first_response_queue: asyncio.Queue[str] = asyncio.Queue()
    entry_id = bus.entry_id
    timeout_map = {a.id: a.timeout_seconds for a in config.agents}
    running_tasks: Dict[str, asyncio.Task] = {}

    def ensure_task(agent_id: str) -> None:
        """Spawn an agent task if one isn't already running."""
        existing = running_tasks.get(agent_id)
        if existing is not None and not existing.done():
            return
        is_entry = agent_id == entry_id
        running_tasks[agent_id] = asyncio.create_task(
            _agent_task(
                agent_id=agent_id,
                agent=agents[agent_id],
                bus=bus,
                task_id=task_id,
                timeout=timeout_map[agent_id],
                is_entry=is_entry,
                first_response_queue=first_response_queue,
                slack_poster=slack_poster,
                ensure_task=ensure_task,
            ),
            name=f"swarm-{task_id}-{agent_id}",
        )
        logger.info(f"[run_swarm] spawned task for {agent_id!r}")

    # Only start the entry agent; workers are spawned when DISPATCHed to.
    ensure_task(entry_id)
    bus.send("__system__", entry_id, request)

    try:
        ack = await asyncio.wait_for(first_response_queue.get(), timeout=120.0)
    except asyncio.TimeoutError:
        logger.error(f"[run_swarm] entry agent did not respond within 120s for {task_id!r}")
        ack = "⏳ Request queued — I'll post updates here as the team works on it."

    return RunResult(answer=ack, task_id=task_id)
