"""
Unit tests for AgentBus — async message routing between agents.

Tests cover:
- Agent registration and deregistration
- One-way async send (sender suspends, resumes on reply)
- Peer-to-peer bidirectional messaging
- Routing to unknown agents raises
- Peer permission enforcement
- Concurrent messages from multiple senders
- Message ordering within a single agent's inbox
- EventType.AGENT integration with existing EventQueue
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from cuga.backend.multi_agent.agent_bus import AgentBus
from cuga.backend.multi_agent.agent_message import AgentMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_echo_handler(agent_id: str, delay: float = 0.0):
    """Returns a handler that echoes the payload back with agent_id prefix."""
    async def handler(message: AgentMessage) -> dict:
        if delay:
            await asyncio.sleep(delay)
        return {"from": agent_id, "echo": message.payload}
    return handler


def make_static_handler(response: dict):
    async def handler(message: AgentMessage) -> dict:
        return response
    return handler


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestAgentBusRegistration:

    def test_register_agent(self):
        bus = AgentBus()
        bus.register("planner", make_echo_handler("planner"))
        assert bus.is_registered("planner")

    def test_unregistered_agent_not_present(self):
        bus = AgentBus()
        assert not bus.is_registered("ghost")

    def test_register_duplicate_raises(self):
        bus = AgentBus()
        bus.register("a", make_echo_handler("a"))
        with pytest.raises(ValueError, match="already registered"):
            bus.register("a", make_echo_handler("a"))

    def test_deregister_removes_agent(self):
        bus = AgentBus()
        bus.register("a", make_echo_handler("a"))
        bus.deregister("a")
        assert not bus.is_registered("a")

    def test_deregister_unknown_raises(self):
        bus = AgentBus()
        with pytest.raises(KeyError):
            bus.deregister("nonexistent")

    def test_registered_agents_list(self):
        bus = AgentBus()
        bus.register("a", make_echo_handler("a"))
        bus.register("b", make_echo_handler("b"))
        assert set(bus.registered_agents()) == {"a", "b"}


# ---------------------------------------------------------------------------
# One-way messaging (send → await reply)
# ---------------------------------------------------------------------------

class TestAgentBusSend:

    async def test_send_and_receive_reply(self):
        bus = AgentBus()
        bus.register("researcher", make_static_handler({"findings": "result"}))

        msg = AgentMessage(
            sender="planner",
            recipient="researcher",
            task_id="t1",
            payload={"query": "research X"},
        )
        reply = await bus.send(msg)
        assert reply["findings"] == "result"

    async def test_sender_receives_correct_reply(self):
        bus = AgentBus()
        bus.register("writer", make_static_handler({"draft": "some text"}))

        reply = await bus.send(AgentMessage(
            sender="researcher", recipient="writer",
            task_id="t1", payload={"findings": ["a", "b"]},
        ))
        assert "draft" in reply

    async def test_send_to_unknown_agent_raises(self):
        bus = AgentBus()
        with pytest.raises(KeyError, match="not registered"):
            await bus.send(AgentMessage(
                sender="planner", recipient="ghost",
                task_id="t1", payload={},
            ))

    async def test_handler_exception_propagates(self):
        async def failing_handler(msg):
            raise RuntimeError("handler blew up")

        bus = AgentBus()
        bus.register("bad_agent", failing_handler)

        with pytest.raises(RuntimeError, match="handler blew up"):
            await bus.send(AgentMessage(
                sender="planner", recipient="bad_agent",
                task_id="t1", payload={},
            ))

    async def test_message_has_unique_id(self):
        m1 = AgentMessage(sender="a", recipient="b", task_id="t1", payload={})
        m2 = AgentMessage(sender="a", recipient="b", task_id="t1", payload={})
        assert m1.id != m2.id

    async def test_timeout_raises(self):
        async def slow_handler(msg):
            await asyncio.sleep(10)
            return {}

        bus = AgentBus(default_timeout=0.05)
        bus.register("slow", slow_handler)

        with pytest.raises(asyncio.TimeoutError):
            await bus.send(AgentMessage(
                sender="planner", recipient="slow",
                task_id="t1", payload={},
            ))


# ---------------------------------------------------------------------------
# Peer-to-peer (peer validation)
# ---------------------------------------------------------------------------

class TestAgentBusPeerValidation:

    async def test_allowed_peer_can_send(self):
        bus = AgentBus()
        bus.register("researcher", make_static_handler({"verified": True}), peers=["fact_checker"])
        bus.register("fact_checker", make_static_handler({"claim": "valid"}), peers=["researcher"])

        reply = await bus.send(AgentMessage(
            sender="fact_checker", recipient="researcher",
            task_id="t1", payload={"claim": "X is true"},
        ))
        assert reply["verified"] is True

    async def test_disallowed_peer_raises(self):
        bus = AgentBus()
        bus.register("researcher", make_static_handler({}), peers=["fact_checker"])
        bus.register("writer", make_static_handler({}), peers=[])  # writer not a peer of researcher

        with pytest.raises(PermissionError, match="not a permitted peer"):
            await bus.send(AgentMessage(
                sender="writer", recipient="researcher",
                task_id="t1", payload={},
            ))

    async def test_no_peer_restriction_allows_all(self):
        """When peers=None (pipeline mode), any registered agent can send."""
        bus = AgentBus()
        bus.register("a", make_static_handler({"ok": True}), peers=None)
        bus.register("b", make_static_handler({}), peers=None)

        reply = await bus.send(AgentMessage(sender="b", recipient="a", task_id="t1", payload={}))
        assert reply["ok"] is True


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestAgentBusConcurrency:

    async def test_multiple_concurrent_senders(self):
        bus = AgentBus()
        bus.register("worker", make_echo_handler("worker", delay=0.01))

        messages = [
            AgentMessage(sender=f"sender_{i}", recipient="worker", task_id="t1", payload={"i": i})
            for i in range(5)
        ]
        replies = await asyncio.gather(*[bus.send(m) for m in messages])
        assert len(replies) == 5

    async def test_inbox_processes_messages_in_order(self):
        received_order = []

        async def ordered_handler(msg):
            received_order.append(msg.payload["seq"])
            return {}

        bus = AgentBus()
        bus.register("target", ordered_handler)

        for seq in range(5):
            await bus.send(AgentMessage(
                sender="source", recipient="target",
                task_id="t1", payload={"seq": seq},
            ))

        assert received_order == list(range(5))

    async def test_agent_can_handle_concurrent_requests(self):
        call_count = {"n": 0}

        async def counting_handler(msg):
            call_count["n"] += 1
            await asyncio.sleep(0.01)
            return {"count": call_count["n"]}

        bus = AgentBus()
        bus.register("counter", counting_handler)

        results = await asyncio.gather(*[
            bus.send(AgentMessage(sender="s", recipient="counter", task_id="t1", payload={}))
            for _ in range(3)
        ])
        assert len(results) == 3


# ---------------------------------------------------------------------------
# EventType.AGENT integration
# ---------------------------------------------------------------------------

class TestAgentBusEventIntegration:

    async def test_uses_event_type_agent(self):
        """AgentBus should use EventType.AGENT when wrapping messages as Events."""
        from cuga.backend.events.models import EventType
        assert hasattr(EventType, "AGENT"), "EventType.AGENT must be added to models.py"
        assert EventType.AGENT == "agent"

    async def test_message_wrapped_as_event(self):
        """Internally, AgentMessage is transported as an Event with type=AGENT."""
        events_seen = []

        async def spy_handler(msg: AgentMessage):
            events_seen.append(msg)
            return {}

        bus = AgentBus()
        bus.register("target", spy_handler)

        await bus.send(AgentMessage(sender="src", recipient="target", task_id="t1", payload={"x": 1}))

        assert len(events_seen) == 1
        assert events_seen[0].payload["x"] == 1
