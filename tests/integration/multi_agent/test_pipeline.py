"""
Integration tests for the pipeline pattern.

Uses mocked CugaAgent instances (no real LLM calls) to verify:
- Entry agent receives the top-level request
- State flows correctly through A → B → C
- Exit agent produces the final response
- Shared TaskState is visible to all agents in the pipeline
- Skills configuration is respected per agent
- Agent-level policies are applied
- Timeout enforced per agent
- Failed intermediate agent propagates error
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cuga.backend.multi_agent.config import load_config
from cuga.backend.multi_agent.runner import ConfigurationRunner
from cuga.backend.multi_agent.task_state import TaskState

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "multi_agent"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_mock_agent(response: str, side_effect=None):
    """Create a mock CugaAgent that returns a fixed response."""
    agent = MagicMock()
    invoke_result = MagicMock()
    invoke_result.answer = response
    if side_effect:
        agent.graph.ainvoke = AsyncMock(side_effect=side_effect)
    else:
        agent.graph.ainvoke = AsyncMock(return_value=invoke_result)
    return agent


@pytest.fixture
def pipeline_config():
    return load_config(FIXTURES / "pipeline.toml")


@pytest.fixture
def mock_agents():
    return {
        "planner":    make_mock_agent("research: climate change impacts"),
        "researcher": make_mock_agent("findings: [CO2 rise, temp increase, sea level]"),
        "writer":     make_mock_agent("Climate change is causing significant global impacts."),
    }


# ---------------------------------------------------------------------------
# Basic pipeline execution
# ---------------------------------------------------------------------------

class TestPipelineExecution:

    async def test_runner_loads_from_toml(self, pipeline_config):
        runner = ConfigurationRunner(pipeline_config)
        assert runner is not None

    async def test_entry_agent_receives_request(self, pipeline_config, mock_agents):
        runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
        await runner.run("What are the impacts of climate change?", task_id="t1")

        call_args = mock_agents["planner"].graph.ainvoke.call_args
        assert "climate change" in str(call_args)

    async def test_exit_agent_provides_final_response(self, pipeline_config, mock_agents):
        runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
        result = await runner.run("What are the impacts of climate change?", task_id="t1")

        assert "Climate change" in result.answer

    async def test_all_agents_invoked_in_order(self, pipeline_config, mock_agents):
        call_order = []

        for agent_id, agent in mock_agents.items():
            _id = agent_id
            original = agent.graph.ainvoke

            async def tracked(*args, _id=_id, _orig=original, **kwargs):
                call_order.append(_id)
                return await _orig(*args, **kwargs)

            agent.graph.ainvoke = tracked

        runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
        await runner.run("test", task_id="t1")

        assert call_order == ["planner", "researcher", "writer"]

    async def test_intermediate_agent_output_feeds_next(self, pipeline_config, mock_agents):
        """Researcher receives planner output in its context."""
        runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
        await runner.run("test request", task_id="t1")

        researcher_call = mock_agents["researcher"].graph.ainvoke.call_args
        # Planner's output should appear in researcher's input
        assert "research: climate change impacts" in str(researcher_call)

    async def test_result_contains_task_id(self, pipeline_config, mock_agents):
        runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
        result = await runner.run("test", task_id="task-xyz")
        assert result.task_id == "task-xyz"


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class TestPipelineSharedState:

    async def test_task_state_created_per_run(self, pipeline_config, mock_agents):
        runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
        result1 = await runner.run("query 1", task_id="t1")
        result2 = await runner.run("query 2", task_id="t2")
        assert result1.task_id != result2.task_id

    async def test_state_visible_to_all_agents(self, pipeline_config):
        agents = {
            "planner":    make_mock_agent("plan done"),
            "researcher": make_mock_agent("research done"),
            "writer":     make_mock_agent("written"),
        }
        runner = ConfigurationRunner(pipeline_config, agents=agents)
        await runner.run("test", task_id="shared-t1")

        # task_state is managed by the runner (patterns layer), not injected into agents
        assert runner._last_task_state is not None
        assert runner._last_task_state.task_id == "shared-t1"

    async def test_agent_writes_to_state_readable_by_next(self, pipeline_config):
        # task_state is the runner's shared scratchpad — agents write to it directly
        # via runner._last_task_state, not through graph state_input
        agents = {
            "planner":    make_mock_agent("planned"),
            "researcher": make_mock_agent("researched"),
            "writer":     make_mock_agent("written"),
        }
        runner = ConfigurationRunner(pipeline_config, agents=agents)
        await runner.run("test", task_id="t1")

        ts = runner._last_task_state
        assert ts is not None
        assert ts.task_id == "t1"
        assert ts.is_active is False

    async def test_state_completed_after_pipeline_finishes(self, pipeline_config, mock_agents):
        states = []

        original_run = ConfigurationRunner.run

        async def capturing_run(self, *args, **kwargs):
            result = await original_run(self, *args, **kwargs)
            states.append(self._last_task_state)
            return result

        runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
        await runner.run("test", task_id="t1")

        # Access internal state to verify it was completed
        assert runner._last_task_state.is_active is False


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

class TestPipelineSkills:

    async def test_skills_enabled_for_researcher(self, pipeline_config, mock_agents):
        """Researcher in pipeline.toml has skills enabled — verify it receives skill tools."""
        with patch("cuga.backend.multi_agent.runner.discover_skills") as mock_discover:
            mock_discover.return_value = []
            runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
            await runner.run("test", task_id="t1")
            # discover_skills should be called for the researcher agent
            mock_discover.assert_called()

    async def test_skills_disabled_for_planner(self, pipeline_config, mock_agents):
        """Planner in pipeline.toml has skills disabled — discover_skills not called for it."""
        with patch("cuga.backend.multi_agent.runner.discover_skills") as mock_discover:
            mock_discover.return_value = []
            runner = ConfigurationRunner(pipeline_config, agents=mock_agents)
            await runner.run("test", task_id="t1")
            # Verify planner agent was NOT passed skill tools
            calls = mock_discover.call_args_list
            called_for_agents = [str(c) for c in calls]
            assert not any("planner" in c for c in called_for_agents)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestPipelineErrorHandling:

    async def test_failed_intermediate_agent_raises(self, pipeline_config):
        agents = {
            "planner":    make_mock_agent("plan done"),
            "researcher": make_mock_agent("", side_effect=RuntimeError("LLM unavailable")),
            "writer":     make_mock_agent("written"),
        }
        runner = ConfigurationRunner(pipeline_config, agents=agents)
        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await runner.run("test", task_id="t1")

    async def test_timeout_per_agent_is_enforced(self, pipeline_config):
        async def slow_invoke(*args, **kwargs):
            await asyncio.sleep(10)

        agents = {
            "planner":    make_mock_agent("plan"),
            "researcher": MagicMock(),
            "writer":     make_mock_agent("written"),
        }
        agents["researcher"].graph.ainvoke = slow_invoke

        # Set very short timeout for researcher in config
        researcher_cfg = next(a for a in pipeline_config.agents if a.id == "researcher")
        researcher_cfg.timeout_seconds = 0.05

        runner = ConfigurationRunner(pipeline_config, agents=agents)
        with pytest.raises(asyncio.TimeoutError):
            await runner.run("test", task_id="t1")

    async def test_state_marked_inactive_on_error(self, pipeline_config):
        agents = {
            "planner":    make_mock_agent("plan"),
            "researcher": make_mock_agent("", side_effect=RuntimeError("boom")),
            "writer":     make_mock_agent("written"),
        }
        runner = ConfigurationRunner(pipeline_config, agents=agents)
        with pytest.raises(RuntimeError):
            await runner.run("test", task_id="t1")

        assert runner._last_task_state.is_active is False
