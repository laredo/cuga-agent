"""
Integration tests for the peer-to-peer pattern.

Verifies:
- Either peer can initiate a message
- Peer permission table is enforced (non-peer cannot send)
- Bidirectional exchange completes correctly
- State is shared across the exchange
- Nested P2P sub-configuration inside a pipeline works
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from cuga.backend.multi_agent.config import load_config
from cuga.backend.multi_agent.runner import ConfigurationRunner
from cuga.backend.multi_agent.agent_bus import AgentBus
from cuga.backend.multi_agent.agent_message import AgentMessage

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "multi_agent"


@pytest.fixture
def p2p_config():
    return load_config(FIXTURES / "peer_to_peer.toml")


@pytest.fixture
def nested_config():
    return load_config(FIXTURES / "nested.toml")


def make_mock_agent(response: str):
    agent = MagicMock()
    result = MagicMock()
    result.answer = response
    agent.graph.ainvoke = AsyncMock(return_value=result)
    return agent


# ---------------------------------------------------------------------------
# Peer permission enforcement
# ---------------------------------------------------------------------------

class TestPeerToPerPermissions:

    async def test_permitted_peer_can_send(self):
        bus = AgentBus()

        async def researcher_handler(msg: AgentMessage):
            return {"verified": True, "claim": msg.payload.get("claim")}

        async def fact_checker_handler(msg: AgentMessage):
            return {"response": "claim checked"}

        bus.register("researcher", researcher_handler, peers=["fact_checker"])
        bus.register("fact_checker", fact_checker_handler, peers=["researcher"])

        reply = await bus.send(AgentMessage(
            sender="fact_checker",
            recipient="researcher",
            task_id="t1",
            payload={"claim": "CO2 is rising"},
        ))
        assert reply["verified"] is True

    async def test_non_peer_cannot_send(self):
        bus = AgentBus()

        bus.register("researcher", AsyncMock(return_value={}), peers=["fact_checker"])
        bus.register("intruder", AsyncMock(return_value={}), peers=[])

        with pytest.raises(PermissionError):
            await bus.send(AgentMessage(
                sender="intruder",
                recipient="researcher",
                task_id="t1",
                payload={},
            ))

    async def test_bidirectional_exchange(self):
        bus = AgentBus()
        exchange_log = []

        async def researcher_handler(msg: AgentMessage):
            exchange_log.append(("researcher", msg.payload))
            return {"findings": "CO2 has risen 50%"}

        async def fact_checker_handler(msg: AgentMessage):
            exchange_log.append(("fact_checker", msg.payload))
            return {"verdict": "verified"}

        bus.register("researcher", researcher_handler, peers=["fact_checker"])
        bus.register("fact_checker", fact_checker_handler, peers=["researcher"])

        # fact_checker initiates
        reply_to_checker = await bus.send(AgentMessage(
            sender="fact_checker", recipient="researcher",
            task_id="t1", payload={"check": "CO2 claim"},
        ))
        # researcher initiates back
        reply_to_researcher = await bus.send(AgentMessage(
            sender="researcher", recipient="fact_checker",
            task_id="t1", payload={"findings": reply_to_checker["findings"]},
        ))

        assert reply_to_checker["findings"] == "CO2 has risen 50%"
        assert reply_to_researcher["verdict"] == "verified"
        assert len(exchange_log) == 2


# ---------------------------------------------------------------------------
# Full P2P runner
# ---------------------------------------------------------------------------

class TestPeerToPerRunner:

    async def test_runner_loads_p2p_config(self, p2p_config):
        assert p2p_config.pattern == "peer_to_peer"

    async def test_entry_agent_runs_first(self, p2p_config):
        call_order = []

        def make_tracking_agent(agent_id: str, response: str):
            agent = MagicMock()
            result = MagicMock()
            result.answer = response

            async def invoke(*args, **kwargs):
                call_order.append(agent_id)
                return result

            agent.graph.ainvoke = invoke
            return agent

        agents = {
            "researcher":   make_tracking_agent("researcher", "research done"),
            "fact_checker": make_tracking_agent("fact_checker", "verified"),
        }
        runner = ConfigurationRunner(p2p_config, agents=agents)
        await runner.run("Research climate impacts", task_id="t1")
        assert call_order[0] == "researcher"

    async def test_final_response_comes_from_exit_agent(self, p2p_config):
        agents = {
            "researcher":   make_mock_agent("research done"),
            "fact_checker": make_mock_agent("verified: all claims accurate"),
        }
        runner = ConfigurationRunner(p2p_config, agents=agents)
        result = await runner.run("test", task_id="t1")
        assert "verified" in result.answer

    async def test_shared_state_across_peers(self, p2p_config):
        # task_state is managed by the runner — verify it exists and is completed
        agents = {
            "researcher":   make_mock_agent("research done"),
            "fact_checker": make_mock_agent("verified"),
        }
        runner = ConfigurationRunner(p2p_config, agents=agents)
        await runner.run("test", task_id="t1")

        ts = runner._last_task_state
        assert ts is not None
        assert ts.task_id == "t1"
        assert ts.is_active is False


# ---------------------------------------------------------------------------
# Nested P2P sub-configuration inside pipeline
# ---------------------------------------------------------------------------

class TestNestedPeerToPerInPipeline:

    async def test_nested_sub_config_executes(self, nested_config):
        assert any(sc.name == "verify" for sc in nested_config.sub_configurations)

    async def test_full_nested_pipeline_runs(self, nested_config):
        agents = {
            "planner":      make_mock_agent("decomposed plan"),
            "researcher":   make_mock_agent("research findings"),
            "fact_checker": make_mock_agent("claims verified"),
            "writer":       make_mock_agent("final answer written"),
        }
        runner = ConfigurationRunner(nested_config, agents=agents)
        result = await runner.run("Research and verify climate change", task_id="nested-t1")
        assert result.answer == "final answer written"

    async def test_peer_validation_within_sub_config(self, nested_config):
        """Agents in the verify sub-config can send to each other but not to agents outside it."""
        runner = ConfigurationRunner(nested_config, agents={
            "planner":      make_mock_agent("plan"),
            "researcher":   make_mock_agent("research"),
            "fact_checker": make_mock_agent("verified"),
            "writer":       make_mock_agent("written"),
        })
        bus = runner.build_bus()

        # researcher ↔ fact_checker is allowed (sub-config peers)
        assert bus.can_send("researcher", "fact_checker")
        assert bus.can_send("fact_checker", "researcher")

        # planner → fact_checker is not allowed (not peers)
        assert not bus.can_send("planner", "fact_checker")
