"""SwarmAgentFactory — extends AgentFactory with per-agent EventQueues and dispatch tools.

For each agent in the topology, ``SwarmAgentFactory`` creates:

  1. An ``EventQueue`` inbox (using the branch's existing event infrastructure).
  2. A LangChain tool named ``dispatch_to_<peer_id>`` for every agent in that
     agent's ``peers`` list.  Calling the tool enqueues an
     ``Event(type=AGENT)`` into the peer's EventQueue immediately — mid-run,
     inside the LangGraph ReAct loop — so fact_checker tasks are spawned one
     per document as web_searcher finds them, not all at once at the end.

Usage (inside run.py for swarm topologies):

    async with SwarmAgentFactory(cfg) as factory:
        runner = ConfigurationRunner(
            cfg,
            agents=factory.agents,
            callbacks=callbacks,
            agent_queues=factory.agent_queues,
        )
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, TYPE_CHECKING

try:
    from langchain_core.runnables import RunnableConfig
except ImportError:
    RunnableConfig = Any

from loguru import logger

from cuga.backend.events.models import Event, EventType, EventSource
from cuga.backend.events.queue import EventQueue
from cuga.backend.multi_agent.agent_factory import AgentFactory

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import AgentConfig, MultiAgentConfig


class SwarmAgentFactory(AgentFactory):
    """AgentFactory variant for the swarm pattern.

    Adds per-agent EventQueues and peer dispatch tools so agents can route
    messages to each other via tool calls during their LangGraph ReAct loop.
    """

    def __init__(self, config: "MultiAgentConfig") -> None:
        super().__init__(config)
        # One EventQueue inbox per agent — created before agents are built
        # so dispatch tool closures can capture live queue references.
        self._agent_queues: Dict[str, EventQueue] = {
            a.id: EventQueue() for a in config.agents
        }

    @property
    def agent_queues(self) -> Dict[str, EventQueue]:
        return self._agent_queues

    # ------------------------------------------------------------------
    # Override _build_agent to inject dispatch tools
    # ------------------------------------------------------------------

    async def _build_agent(self, agent_cfg: "AgentConfig") -> Any:
        from cuga.sdk import CugaAgent

        mcp_tools = await self._load_mcp_tools(agent_cfg.mcp_servers)
        dispatch_tools = self._make_dispatch_tools(agent_cfg)
        all_tools = mcp_tools + dispatch_tools

        agent = CugaAgent(
            tools=all_tools or None,
            special_instructions=agent_cfg.instructions,
            enable_knowledge=agent_cfg.enable_knowledge,
        )

        if agent_cfg.enable_knowledge:
            self._inject_kb_scope(agent, agent_cfg.id)

        if dispatch_tools:
            tool_names = [t.name for t in dispatch_tools]
            logger.info(f"[SwarmAgentFactory] {agent_cfg.id}: injected dispatch tools {tool_names}")

        return agent

    # ------------------------------------------------------------------
    # Build dispatch tools for this agent's declared peers
    # ------------------------------------------------------------------

    def _make_dispatch_tools(self, agent_cfg: "AgentConfig") -> List[Any]:
        """Return one LangChain tool per declared peer."""
        try:
            from langchain_core.tools import StructuredTool
            from langchain_core.runnables import RunnableConfig
        except ImportError:
            logger.warning("langchain_core not available — dispatch tools skipped")
            return []

        tools = []
        sender_id = agent_cfg.id

        for peer_id in agent_cfg.peers:
            peer_queue = self._agent_queues.get(peer_id)
            if peer_queue is None:
                logger.warning(f"[SwarmAgentFactory] peer {peer_id!r} not in topology — skipping")
                continue

            # Capture peer_id and peer_queue in default args (avoids late-binding)
            async def _dispatch_fn(
                content: str,
                config: Optional[RunnableConfig] = None,
                _peer_id: str = peer_id,
                _sender_id: str = sender_id,
                _queue: EventQueue = peer_queue,
                **kwargs,
            ) -> str:
                """Enqueue content to a peer agent's event queue."""
                thread_id = ""
                if config and hasattr(config, "get"):
                    thread_id = config.get("configurable", {}).get("thread_id", "")
                
                if not thread_id:
                    thread_id = kwargs.get("thread_id", "")

                task_id = thread_id.split("-")[0] if thread_id else ""

                event = Event(
                    type=EventType.AGENT,
                    source=EventSource.INTERNAL,
                    event_name="agent_dispatch",
                    payload={"sender": _sender_id, "recipient": _peer_id, "content": content, "task_id": task_id},
                )
                await _queue.enqueue(event)
                logger.info(f"[dispatch] {_sender_id} → {_peer_id} ({len(content)} chars)")
                return f"✓ Dispatched to {_peer_id}"

            tool_name = f"dispatch_to_{peer_id}"
            tool_description = (
                f"Send content to {peer_id} for immediate, concurrent processing. "
                f"Call this as soon as you have a result ready — "
                f"do NOT wait to collect all results before dispatching. "
                f"Each call spawns an independent {peer_id} task."
            )

            tool = StructuredTool.from_function(
                coroutine=_dispatch_fn,
                name=tool_name,
                description=tool_description,
            )
            tools.append(tool)

        return tools
