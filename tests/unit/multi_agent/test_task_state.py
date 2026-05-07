"""
Unit tests for TaskState — per-task namespaced shared state.

Tests cover:
- Namespace isolation between agents
- Read/write lifecycle
- Task completion and cleanup
- Concurrent access safety
- Lesson harvesting hook
"""

import asyncio
import pytest

from cuga.backend.multi_agent.task_state import TaskState


class TestTaskStateCreation:

    def test_creates_with_task_id(self):
        state = TaskState(task_id="abc-123")
        assert state.task_id == "abc-123"

    def test_initial_state_is_empty(self):
        state = TaskState(task_id="t1")
        assert state.get("planner") == {}
        assert state.get("researcher") == {}

    def test_is_active_on_creation(self):
        state = TaskState(task_id="t1")
        assert state.is_active is True


class TestTaskStateNamespacing:

    def test_write_and_read_own_namespace(self):
        state = TaskState(task_id="t1")
        state.set("researcher", "findings", ["fact A", "fact B"])
        assert state.get("researcher")["findings"] == ["fact A", "fact B"]

    def test_namespaces_are_isolated(self):
        state = TaskState(task_id="t1")
        state.set("researcher", "findings", "research result")
        state.set("writer", "draft", "draft text")
        assert "draft" not in state.get("researcher")
        assert "findings" not in state.get("writer")

    def test_overwrite_existing_key(self):
        state = TaskState(task_id="t1")
        state.set("planner", "plan", "v1")
        state.set("planner", "plan", "v2")
        assert state.get("planner")["plan"] == "v2"

    def test_multiple_keys_in_namespace(self):
        state = TaskState(task_id="t1")
        state.set("researcher", "findings", ["a"])
        state.set("researcher", "sources", ["url1"])
        state.set("researcher", "status", "done")
        ns = state.get("researcher")
        assert ns["findings"] == ["a"]
        assert ns["sources"] == ["url1"]
        assert ns["status"] == "done"

    def test_get_returns_copy_not_reference(self):
        """Mutations to returned dict should not affect stored state."""
        state = TaskState(task_id="t1")
        state.set("agent", "data", [1, 2, 3])
        ns = state.get("agent")
        ns["data"].append(4)
        assert state.get("agent")["data"] == [1, 2, 3]

    def test_get_all_returns_full_snapshot(self):
        state = TaskState(task_id="t1")
        state.set("a", "x", 1)
        state.set("b", "y", 2)
        snapshot = state.get_all()
        assert snapshot["a"]["x"] == 1
        assert snapshot["b"]["y"] == 2
        assert "task_id" in snapshot

    def test_task_id_in_snapshot(self):
        state = TaskState(task_id="my-task-99")
        assert state.get_all()["task_id"] == "my-task-99"


class TestTaskStateLifecycle:

    def test_complete_marks_inactive(self):
        state = TaskState(task_id="t1")
        state.complete()
        assert state.is_active is False

    def test_write_after_complete_raises(self):
        state = TaskState(task_id="t1")
        state.complete()
        with pytest.raises(RuntimeError, match="completed"):
            state.set("agent", "key", "value")

    def test_read_after_complete_still_works(self):
        state = TaskState(task_id="t1")
        state.set("agent", "key", "value")
        state.complete()
        assert state.get("agent")["key"] == "value"

    def test_complete_is_idempotent(self):
        state = TaskState(task_id="t1")
        state.complete()
        state.complete()  # should not raise
        assert state.is_active is False


class TestTaskStateLessonHarvesting:

    def test_on_complete_hook_called(self):
        harvested = {}

        def harvest(snapshot):
            harvested.update(snapshot)

        state = TaskState(task_id="t1", on_complete=harvest)
        state.set("agent", "result", "success")
        state.complete()

        assert harvested["agent"]["result"] == "success"
        assert harvested["task_id"] == "t1"

    def test_on_complete_hook_not_called_if_not_provided(self):
        state = TaskState(task_id="t1")
        state.complete()  # should not raise


class TestTaskStateConcurrency:

    async def test_concurrent_writes_to_different_namespaces(self):
        state = TaskState(task_id="t1")

        async def write_agent(agent_id: str, value: str):
            await asyncio.sleep(0)  # yield
            state.set(agent_id, "result", value)

        await asyncio.gather(
            write_agent("agent_a", "result_a"),
            write_agent("agent_b", "result_b"),
            write_agent("agent_c", "result_c"),
        )

        assert state.get("agent_a")["result"] == "result_a"
        assert state.get("agent_b")["result"] == "result_b"
        assert state.get("agent_c")["result"] == "result_c"

    async def test_concurrent_reads_are_safe(self):
        state = TaskState(task_id="t1")
        state.set("shared", "data", list(range(100)))

        async def _read():
            return state.get("shared")

        results = await asyncio.gather(*[_read() for _ in range(10)])

        for r in results:
            assert r["data"] == list(range(100))
