"""Swarm pattern: concurrent agent tasks with asyncio.Queue inboxes and peer ACL.

Routing convention — agents embed directives in their plain-text output:

    DISPATCH:<agent_id>
    <content to deliver to that agent>

    DISPATCH:<another_agent_id>
    <separate content block>

    DONE:<final answer returned to the caller>

Rules enforced by SwarmBus:
  • sender may send to any agent listed in its ``peers`` field (from topology)
  • any agent may additionally send to the entry agent (completion reports)
  • ``__system__`` is exempt — used to seed the entry agent's inbox

Non-directive lines in agent output (before the first DISPATCH or after DONE)
are silently dropped; agents can use them for chain-of-thought reasoning that
should not be routed anywhere.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from loguru import logger

from cuga.backend.multi_agent.patterns.pipeline import (
    RunResult,
    _build_graph_state,
    _extract_answer,
)

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import AgentConfig, MultiAgentConfig
    from cuga.backend.multi_agent.task_state import TaskState


# ---------------------------------------------------------------------------
# Message envelope
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SwarmMessage:
    sender: str
    content: str


_SHUTDOWN = SwarmMessage(sender="__shutdown__", content="")


# ---------------------------------------------------------------------------
# SwarmBus
# ---------------------------------------------------------------------------

class SwarmBus:
    """Per-agent asyncio.Queue inboxes with peer ACL enforcement.

    ACL:
      * sender → recipient  allowed when  ``recipient in sender.peers``
      * any agent           → entry agent always allowed (completion reports)
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

    async def receive(self, agent_id: str) -> SwarmMessage:
        return await self._queues[agent_id].get()

    def shutdown(self) -> None:
        """Unblock all waiting agent tasks by delivering the shutdown sentinel."""
        for q in self._queues.values():
            q.put_nowait(_SHUTDOWN)


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

def _parse_output(raw: str) -> Tuple[Optional[str], List[Tuple[str, str]]]:
    """Extract DISPATCH and DONE directives from *raw* agent output.

    Returns ``(done_text, [(recipient, content), …])``.
    ``done_text`` is non-None when DONE: was found; signals swarm termination.
    """
    done_text: Optional[str] = None
    dispatches: List[Tuple[str, str]] = []
    current_recipient: Optional[str] = None
    current_lines: List[str] = []

    def _flush() -> None:
        if current_recipient is not None:
            dispatches.append((current_recipient, "\n".join(current_lines).strip()))

    for line in raw.splitlines():
        stripped = line.strip()
        upper = stripped.upper()

        if upper.startswith("DISPATCH:"):
            _flush()
            current_recipient = stripped[len("DISPATCH:"):].strip()
            current_lines = []
        elif upper.startswith("DONE:"):
            _flush()
            current_recipient = None
            current_lines = []
            done_text = stripped[len("DONE:"):].strip()
        elif current_recipient is not None:
            current_lines.append(line)
        # Lines outside any directive block are intentionally ignored.

    _flush()
    return done_text, dispatches


# ---------------------------------------------------------------------------
# Agent task
# ---------------------------------------------------------------------------

async def _agent_task(
    agent_id: str,
    agent: Any,
    bus: SwarmBus,
    task_id: str,
    timeout: int,
    done_event: asyncio.Event,
    final_queue: asyncio.Queue[str],
) -> None:
    """Message loop: dequeue → invoke LLM → parse directives → route."""
    while not done_event.is_set():
        msg = await bus.receive(agent_id)

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
            logger.warning(f"[swarm:{agent_id}] timed out after {timeout}s")
            continue
        except Exception as exc:
            logger.error(f"[swarm:{agent_id}] error: {exc}")
            continue

        answer = _extract_answer(result)
        done_text, dispatches = _parse_output(answer)

        for recipient, content in dispatches:
            try:
                bus.send(agent_id, recipient, content)
            except (PermissionError, ValueError) as exc:
                logger.warning(f"[swarm:{agent_id}] routing skipped: {exc}")

        if done_text is not None:
            logger.info(f"[swarm:{agent_id}] DONE signal emitted")
            await final_queue.put(done_text)
            done_event.set()
            return


# ---------------------------------------------------------------------------
# run_swarm
# ---------------------------------------------------------------------------

async def run_swarm(
    config: "MultiAgentConfig",
    agents: Dict[str, Any],
    request: str,
    task_id: str,
    task_state: "TaskState",
    callbacks: Optional[List[Any]] = None,
) -> RunResult:
    """Launch all agents as concurrent asyncio.Tasks and drive them via SwarmBus.

    Terminates when any agent emits a ``DONE:`` directive.  The text after
    ``DONE:`` becomes the final answer returned to the caller.
    """
    bus = SwarmBus(config.agents)
    done_event = asyncio.Event()
    final_queue: asyncio.Queue[str] = asyncio.Queue()

    timeout_map = {a.id: a.timeout_seconds for a in config.agents}

    agent_tasks = [
        asyncio.create_task(
            _agent_task(
                agent_id=a.id,
                agent=agents[a.id],
                bus=bus,
                task_id=task_id,
                timeout=timeout_map[a.id],
                done_event=done_event,
                final_queue=final_queue,
            ),
            name=f"swarm-{a.id}",
        )
        for a in config.agents
    ]

    # Bootstrap: seed the entry agent's inbox with the user request.
    bus.send("__system__", bus.entry_id, request)

    final_answer = ""
    try:
        await asyncio.wait_for(done_event.wait(), timeout=600.0)
        final_answer = final_queue.get_nowait() if not final_queue.empty() else ""
    except asyncio.TimeoutError:
        logger.error(f"[run_swarm] task {task_id!r} timed out after 600s")
        final_answer = "❌ Swarm timed out — no DONE signal received within 10 minutes."
    finally:
        done_event.set()
        bus.shutdown()
        await asyncio.gather(*agent_tasks, return_exceptions=True)

    return RunResult(answer=final_answer, task_id=task_id)
