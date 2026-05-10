"""Unit tests for SwarmAgentFactory — no LLM, no Slack, no MCP connections.

Covers:
- Per-agent EventQueue isolation (each agent gets its own queue instance)
- Dispatch tool ACL: only peers declared in topology get a dispatch tool
- Tool naming convention: dispatch_to_{peer_id}
- Closure correctness: each tool enqueues to the right queue (not last-bound)
- Payload structure: Event fields sender / recipient / content
- agents with peers=[] receive zero dispatch tools
"""

from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cuga.backend.events.models import Event, EventType
from cuga.backend.events.queue import EventQueue
from cuga.backend.multi_agent.config import AgentConfig, MultiAgentConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_cfg(agent_id: str, peers: List[str], role: str = "worker") -> AgentConfig:
    return AgentConfig(id=agent_id, type="cuga_lite", domain="test", role=role, peers=peers)


def _config(*agents: AgentConfig) -> MultiAgentConfig:
    """Build a valid MultiAgentConfig — promotes the first agent to entry if none declared."""
    agent_list = list(agents)
    has_entry = any(a.role == "entry" for a in agent_list)
    if not has_entry and agent_list:
        # Replace first agent with an entry-role copy
        first = agent_list[0]
        agent_list[0] = AgentConfig(
            id=first.id, type=first.type, domain=first.domain,
            role="entry", peers=first.peers,
        )
    # MultiAgentConfig requires at least 2 agents
    if len(agent_list) == 1:
        agent_list.append(AgentConfig(id="_dummy", type="cuga_lite", domain="test", role="worker"))
    return MultiAgentConfig(name="test_swarm", pattern="swarm", agents=agent_list)


async def _queue_is_empty(queue, timeout: float = 0.15) -> bool:
    """Return True if the queue has no pending event within timeout seconds."""
    try:
        ev = await asyncio.wait_for(queue.dequeue(), timeout=timeout)
        return ev is None
    except asyncio.TimeoutError:
        return True


# ---------------------------------------------------------------------------
# Import the factory with MCP loading patched out so no network calls happen
# ---------------------------------------------------------------------------

@pytest.fixture()
def factory_cls():
    """Return SwarmAgentFactory with _load_mcp_tools and _build_agent stubbed."""
    with patch(
        "cuga.backend.multi_agent.agent_factory.AgentFactory._load_mcp_tools",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "cuga.backend.multi_agent.swarm_factory.SwarmAgentFactory._build_agent",
        new_callable=AsyncMock,
        return_value=MagicMock(),
    ):
        from cuga.backend.multi_agent.swarm_factory import SwarmAgentFactory
        yield SwarmAgentFactory


# ---------------------------------------------------------------------------
# EventQueue isolation
# ---------------------------------------------------------------------------

class TestEventQueueIsolation:

    def test_each_agent_gets_own_queue(self, factory_cls):
        cfg = _config(
            _agent_cfg("chief_of_staff", peers=["web_searcher"], role="entry"),
            _agent_cfg("web_searcher", peers=["fact_checker"]),
            _agent_cfg("fact_checker", peers=[]),
        )
        factory = factory_cls(cfg)
        queues = factory.agent_queues

        assert set(queues.keys()) == {"chief_of_staff", "web_searcher", "fact_checker"}
        # All queue objects must be distinct instances
        queue_ids = [id(q) for q in queues.values()]
        assert len(queue_ids) == len(set(queue_ids)), "Agents share an EventQueue instance"

    def test_queues_are_event_queue_instances(self, factory_cls):
        cfg = _config(_agent_cfg("agent_a", peers=[]))
        factory = factory_cls(cfg)
        for q in factory.agent_queues.values():
            assert isinstance(q, EventQueue)

    def test_queue_count_matches_agent_count(self, factory_cls):
        agents = [_agent_cfg(f"agent_{i}", peers=[]) for i in range(5)]
        cfg = _config(*agents)
        factory = factory_cls(cfg)
        assert len(factory.agent_queues) == 5


# ---------------------------------------------------------------------------
# Dispatch tool ACL and naming
# ---------------------------------------------------------------------------

class TestDispatchToolCreation:

    def test_tool_created_for_each_declared_peer(self, factory_cls):
        cfg = _config(
            _agent_cfg("chief_of_staff", peers=["web_searcher", "summarizer"], role="entry"),
            _agent_cfg("web_searcher", peers=["fact_checker"]),
            _agent_cfg("fact_checker", peers=[]),
            _agent_cfg("summarizer", peers=[]),
        )
        factory = factory_cls(cfg)

        cs_tools = factory._make_dispatch_tools(cfg.agents[0])
        assert len(cs_tools) == 2
        tool_names = {t.name for t in cs_tools}
        assert tool_names == {"dispatch_to_web_searcher", "dispatch_to_summarizer"}

        ws_tools = factory._make_dispatch_tools(cfg.agents[1])
        assert len(ws_tools) == 1
        assert ws_tools[0].name == "dispatch_to_fact_checker"

    def test_agent_with_no_peers_gets_no_tools(self, factory_cls):
        cfg = _config(
            _agent_cfg("fact_checker", peers=[]),
        )
        factory = factory_cls(cfg)
        tools = factory._make_dispatch_tools(cfg.agents[0])
        assert tools == []

    def test_tool_names_follow_convention(self, factory_cls):
        cfg = _config(
            _agent_cfg("sender", peers=["receiver_one", "receiver_two"]),
            _agent_cfg("receiver_one", peers=[]),
            _agent_cfg("receiver_two", peers=[]),
        )
        factory = factory_cls(cfg)
        tools = factory._make_dispatch_tools(cfg.agents[0])
        for tool in tools:
            assert tool.name.startswith("dispatch_to_")

    def test_unknown_peer_skipped_gracefully(self, factory_cls):
        """A peer_id not in the topology should be silently skipped."""
        cfg = _config(
            _agent_cfg("sender", peers=["ghost_agent"]),
        )
        factory = factory_cls(cfg)
        # ghost_agent has no EventQueue → tool should be skipped, not crash
        tools = factory._make_dispatch_tools(cfg.agents[0])
        assert tools == []


# ---------------------------------------------------------------------------
# Closure correctness (late-binding guard)
# ---------------------------------------------------------------------------

class TestDispatchToolClosures:

    @pytest.mark.asyncio
    async def test_each_tool_enqueues_to_correct_queue(self, factory_cls):
        """Five tools, each must write to its own queue — not all to the last one."""
        peers = [f"peer_{i}" for i in range(5)]
        agents = [_agent_cfg("sender", peers=peers)] + [
            _agent_cfg(p, peers=[]) for p in peers
        ]
        cfg = _config(*agents)
        factory = factory_cls(cfg)

        tools = factory._make_dispatch_tools(cfg.agents[0])
        assert len(tools) == 5

        for tool in tools:
            await tool.coroutine(content=f"msg for {tool.name}")

        for peer_id in peers:
            q = factory.agent_queues[peer_id]
            # Expect exactly 1 event — dequeue it, then confirm queue is now empty
            ev = await asyncio.wait_for(q.dequeue(), timeout=1.0)
            assert ev is not None, f"{peer_id} got no event — possible late-binding bug"
            assert ev.payload["recipient"] == peer_id, (
                f"Event landed in {peer_id}'s queue but recipient={ev.payload['recipient']}"
            )
            assert await _queue_is_empty(q), f"{peer_id} has more than 1 event"

    @pytest.mark.asyncio
    async def test_tool_does_not_cross_enqueue(self, factory_cls):
        """dispatch_to_fact_checker must not enqueue into web_searcher's queue."""
        cfg = _config(
            _agent_cfg("web_searcher", peers=["fact_checker"], role="entry"),
            _agent_cfg("fact_checker", peers=[]),
        )
        factory = factory_cls(cfg)
        tools = {t.name: t for t in factory._make_dispatch_tools(cfg.agents[0])}

        await tools["dispatch_to_fact_checker"].coroutine(content="a document")

        # fact_checker queue should have the event
        fc_q = factory.agent_queues["fact_checker"]
        ev = await asyncio.wait_for(fc_q.dequeue(), timeout=1.0)
        assert ev is not None

        # web_searcher queue must be empty
        ws_q = factory.agent_queues["web_searcher"]
        assert await _queue_is_empty(ws_q), "web_searcher queue unexpectedly has an event"


# ---------------------------------------------------------------------------
# Event payload structure
# ---------------------------------------------------------------------------

class TestDispatchEventPayload:

    @pytest.mark.asyncio
    async def test_event_type_is_agent(self, factory_cls):
        cfg = _config(
            _agent_cfg("sender", peers=["receiver"]),
            _agent_cfg("receiver", peers=[]),
        )
        factory = factory_cls(cfg)
        tool = factory._make_dispatch_tools(cfg.agents[0])[0]
        await tool.coroutine(content="hello")

        ev: Event = await asyncio.wait_for(
            factory.agent_queues["receiver"].dequeue(), timeout=1.0
        )
        assert ev.type == EventType.AGENT

    @pytest.mark.asyncio
    async def test_payload_contains_sender_recipient_content(self, factory_cls):
        cfg = _config(
            _agent_cfg("chief_of_staff", peers=["web_searcher"], role="entry"),
            _agent_cfg("web_searcher", peers=[]),
        )
        factory = factory_cls(cfg)
        tool = factory._make_dispatch_tools(cfg.agents[0])[0]
        await tool.coroutine(content="research quantum computing")

        ev: Event = await asyncio.wait_for(
            factory.agent_queues["web_searcher"].dequeue(), timeout=1.0
        )
        assert ev.payload["sender"] == "chief_of_staff"
        assert ev.payload["recipient"] == "web_searcher"
        assert ev.payload["content"] == "research quantum computing"

    @pytest.mark.asyncio
    async def test_tool_returns_confirmation_string(self, factory_cls):
        cfg = _config(
            _agent_cfg("sender", peers=["receiver"]),
            _agent_cfg("receiver", peers=[]),
        )
        factory = factory_cls(cfg)
        tool = factory._make_dispatch_tools(cfg.agents[0])[0]
        result = await tool.coroutine(content="test")
        assert "receiver" in result
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_content_preserved_exactly(self, factory_cls):
        """Multiline content with special chars must arrive intact."""
        cfg = _config(
            _agent_cfg("sender", peers=["receiver"]),
            _agent_cfg("receiver", peers=[]),
        )
        factory = factory_cls(cfg)
        tool = factory._make_dispatch_tools(cfg.agents[0])[0]

        content = "Title: Test\nURL: https://example.com\nScore: 5/5\n🔍 verified"
        await tool.coroutine(content=content)

        ev: Event = await asyncio.wait_for(
            factory.agent_queues["receiver"].dequeue(), timeout=1.0
        )
        assert ev.payload["content"] == content

    @pytest.mark.asyncio
    async def test_multiple_dispatches_queue_in_order(self, factory_cls):
        cfg = _config(
            _agent_cfg("sender", peers=["receiver"]),
            _agent_cfg("receiver", peers=[]),
        )
        factory = factory_cls(cfg)
        tool = factory._make_dispatch_tools(cfg.agents[0])[0]

        messages = ["doc_1", "doc_2", "doc_3"]
        for msg in messages:
            await tool.coroutine(content=msg)

        q = factory.agent_queues["receiver"]
        received = []
        for _ in messages:
            ev = await asyncio.wait_for(q.dequeue(), timeout=1.0)
            received.append(ev.payload["content"])

        assert received == messages
