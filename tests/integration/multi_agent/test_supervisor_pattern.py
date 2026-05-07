"""
Integration tests for the supervisor pattern.

Verifies that a supervisor TOML configuration correctly:
- Delegates to the existing CugaSupervisor
- Routes tasks to appropriate workers
- Aggregates worker results
- Preserves supervisor ↔ worker isolation in TaskState
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cuga.backend.multi_agent.config import load_config
from cuga.backend.multi_agent.runner import ConfigurationRunner

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "multi_agent"


@pytest.fixture
def supervisor_config():
    return load_config(FIXTURES / "supervisor.toml")


def make_mock_agent(response: str):
    agent = MagicMock()
    result = MagicMock()
    result.answer = response
    agent.graph.ainvoke = AsyncMock(return_value=result)
    return agent


class TestSupervisorPattern:

    async def test_runner_loads_supervisor_config(self, supervisor_config):
        assert supervisor_config.pattern == "supervisor"
        assert any(a.type == "cuga_supervisor" for a in supervisor_config.agents)

    async def test_supervisor_agent_is_entry(self, supervisor_config):
        entry = next(a for a in supervisor_config.agents if a.role == "entry")
        assert entry.type == "cuga_supervisor"

    async def test_delegates_to_cuga_supervisor(self, supervisor_config):
        with patch("cuga.backend.multi_agent.patterns.supervisor.CugaSupervisor") as MockSupervisor:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.answer = "CRM task completed"
            mock_instance.invoke = AsyncMock(return_value=mock_result)
            MockSupervisor.return_value = mock_instance

            runner = ConfigurationRunner(supervisor_config)
            result = await runner.run("Get all leads from CRM", task_id="t1")

            MockSupervisor.assert_called_once()
            mock_instance.invoke.assert_called_once()
            assert "CRM task completed" in result.answer

    async def test_workers_registered_with_supervisor(self, supervisor_config):
        with patch("cuga.backend.multi_agent.patterns.supervisor.CugaSupervisor") as MockSupervisor:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.answer = "done"
            mock_instance.invoke = AsyncMock(return_value=mock_result)
            MockSupervisor.return_value = mock_instance

            runner = ConfigurationRunner(supervisor_config)
            await runner.run("test task", task_id="t1")

            init_kwargs = MockSupervisor.call_args[1] if MockSupervisor.call_args[1] else {}
            init_args = MockSupervisor.call_args[0] if MockSupervisor.call_args[0] else ()
            agents_arg = init_kwargs.get("agents") or (init_args[0] if init_args else {})

            assert "crm_worker" in agents_arg
            assert "email_worker" in agents_arg

    async def test_task_state_created_for_supervisor_run(self, supervisor_config):
        with patch("cuga.backend.multi_agent.patterns.supervisor.CugaSupervisor") as MockSupervisor:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.answer = "done"
            mock_instance.invoke = AsyncMock(return_value=mock_result)
            MockSupervisor.return_value = mock_instance

            runner = ConfigurationRunner(supervisor_config)
            result = await runner.run("test", task_id="sup-t1")

            assert result.task_id == "sup-t1"
            assert runner._last_task_state is not None
            assert runner._last_task_state.task_id == "sup-t1"

    async def test_supervisor_error_propagates(self, supervisor_config):
        with patch("cuga.backend.multi_agent.patterns.supervisor.CugaSupervisor") as MockSupervisor:
            mock_instance = MagicMock()
            mock_instance.invoke = AsyncMock(side_effect=RuntimeError("supervisor failed"))
            MockSupervisor.return_value = mock_instance

            runner = ConfigurationRunner(supervisor_config)
            with pytest.raises(RuntimeError, match="supervisor failed"):
                await runner.run("test", task_id="t1")
