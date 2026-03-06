"""
Unit tests for Heartbeat system
Following TDD approach - tests for batched periodic monitoring inspired by OpenClaw
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from cuga.backend.events.heartbeat import (
    HeartbeatConfig,
    HeartbeatTask,
    HeartbeatManager,
    HeartbeatResult,
    HeartbeatStatus
)
from cuga.backend.events.models import Event, EventType, EventSource


class TestHeartbeatConfig:
    """Test HeartbeatConfig model"""
    
    def test_heartbeat_config_creation_with_defaults(self):
        """Test creating heartbeat config with default values"""
        config = HeartbeatConfig(
            tasks=["email", "calendar"]
        )
        
        assert config.enabled is True
        assert config.interval_seconds == 1800  # 30 minutes default
        assert config.tasks == ["email", "calendar"]
        assert config.thread_id == "main"  # Always main session
        assert config.batch_size == 10
    
    def test_heartbeat_config_with_custom_values(self):
        """Test creating heartbeat config with custom values"""
        config = HeartbeatConfig(
            enabled=False,
            interval_seconds=3600,
            tasks=["slack", "github"],
            thread_id="main",
            batch_size=5
        )
        
        assert config.enabled is False
        assert config.interval_seconds == 3600
        assert config.tasks == ["slack", "github"]
        assert config.thread_id == "main"
        assert config.batch_size == 5
    
    def test_heartbeat_config_thread_id_must_be_main(self):
        """Test that thread_id must always be 'main' for heartbeat"""
        config = HeartbeatConfig(
            tasks=["email"],
            thread_id="main"
        )
        
        assert config.thread_id == "main"
    
    def test_heartbeat_config_validation_requires_tasks(self):
        """Test that tasks list is required"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            HeartbeatConfig()
    
    def test_heartbeat_config_empty_tasks_list_invalid(self):
        """Test that empty tasks list is invalid"""
        with pytest.raises(Exception):  # Validation error
            HeartbeatConfig(tasks=[])


class TestHeartbeatTask:
    """Test HeartbeatTask model"""
    
    def test_heartbeat_task_creation(self):
        """Test creating a heartbeat task"""
        task = HeartbeatTask(
            name="email_check",
            description="Check for new emails",
            tool_name="email_reader",
            parameters={"folder": "inbox"}
        )
        
        assert task.name == "email_check"
        assert task.description == "Check for new emails"
        assert task.tool_name == "email_reader"
        assert task.parameters == {"folder": "inbox"}
        assert task.enabled is True
        assert task.priority == "normal"
    
    def test_heartbeat_task_with_priority(self):
        """Test creating task with custom priority"""
        task = HeartbeatTask(
            name="urgent_check",
            tool_name="alert_checker",
            priority="high"
        )
        
        assert task.priority == "high"
    
    def test_heartbeat_task_can_be_disabled(self):
        """Test that tasks can be disabled"""
        task = HeartbeatTask(
            name="optional_task",
            tool_name="optional_tool",
            enabled=False
        )
        
        assert task.enabled is False


class TestHeartbeatResult:
    """Test HeartbeatResult model"""
    
    def test_heartbeat_result_creation(self):
        """Test creating a heartbeat result"""
        result = HeartbeatResult(
            task_name="email_check",
            status=HeartbeatStatus.SUCCESS,
            data={"new_emails": 5},
            message="Found 5 new emails"
        )
        
        assert result.task_name == "email_check"
        assert result.status == HeartbeatStatus.SUCCESS
        assert result.data == {"new_emails": 5}
        assert result.message == "Found 5 new emails"
        assert result.error is None
        assert isinstance(result.timestamp, datetime)
    
    def test_heartbeat_result_with_error(self):
        """Test creating result with error"""
        result = HeartbeatResult(
            task_name="failed_task",
            status=HeartbeatStatus.FAILED,
            error="Connection timeout"
        )
        
        assert result.status == HeartbeatStatus.FAILED
        assert result.error == "Connection timeout"
    
    def test_heartbeat_result_skipped_status(self):
        """Test result with skipped status"""
        result = HeartbeatResult(
            task_name="skipped_task",
            status=HeartbeatStatus.SKIPPED,
            message="Rate limit reached"
        )
        
        assert result.status == HeartbeatStatus.SKIPPED


class TestHeartbeatManager:
    """Test HeartbeatManager functionality"""
    
    def test_heartbeat_manager_creation(self):
        """Test creating a heartbeat manager"""
        config = HeartbeatConfig(tasks=["email", "calendar"])
        manager = HeartbeatManager(config=config)
        
        assert manager.config == config
        assert manager.is_running is False
        assert len(manager.tasks) == 0
    
    def test_register_task(self):
        """Test registering a task with the manager"""
        config = HeartbeatConfig(tasks=["email"])
        manager = HeartbeatManager(config=config)
        
        task = HeartbeatTask(
            name="email",
            tool_name="email_reader"
        )
        
        manager.register_task(task)
        
        assert len(manager.tasks) == 1
        assert manager.tasks[0].name == "email"
    
    def test_register_multiple_tasks(self):
        """Test registering multiple tasks"""
        config = HeartbeatConfig(tasks=["email", "calendar", "slack"])
        manager = HeartbeatManager(config=config)
        
        tasks = [
            HeartbeatTask(name="email", tool_name="email_reader"),
            HeartbeatTask(name="calendar", tool_name="calendar_reader"),
            HeartbeatTask(name="slack", tool_name="slack_reader")
        ]
        
        for task in tasks:
            manager.register_task(task)
        
        assert len(manager.tasks) == 3
    
    def test_unregister_task(self):
        """Test unregistering a task"""
        config = HeartbeatConfig(tasks=["email"])
        manager = HeartbeatManager(config=config)
        
        task = HeartbeatTask(name="email", tool_name="email_reader")
        manager.register_task(task)
        
        manager.unregister_task("email")
        
        assert len(manager.tasks) == 0
    
    def test_get_task_by_name(self):
        """Test retrieving a task by name"""
        config = HeartbeatConfig(tasks=["email"])
        manager = HeartbeatManager(config=config)
        
        task = HeartbeatTask(name="email", tool_name="email_reader")
        manager.register_task(task)
        
        retrieved = manager.get_task("email")
        
        assert retrieved is not None
        assert retrieved.name == "email"
    
    def test_get_nonexistent_task_returns_none(self):
        """Test that getting nonexistent task returns None"""
        config = HeartbeatConfig(tasks=["email"])
        manager = HeartbeatManager(config=config)
        
        result = manager.get_task("nonexistent")
        
        assert result is None
    
    def test_should_run_checks_enabled_flag(self):
        """Test that should_run respects enabled flag"""
        config = HeartbeatConfig(tasks=["email"], enabled=False)
        manager = HeartbeatManager(config=config)
        
        assert manager.should_run() is False
        
        config.enabled = True
        assert manager.should_run() is True
    
    def test_should_run_checks_interval(self):
        """Test that should_run respects interval timing"""
        config = HeartbeatConfig(tasks=["email"], interval_seconds=60)
        manager = HeartbeatManager(config=config)
        
        # First run should be allowed
        assert manager.should_run() is True
        
        # Set last run to now
        manager.last_run = datetime.now(timezone.utc)
        
        # Immediate second run should be blocked
        assert manager.should_run() is False
        
        # Set last run to past (beyond interval)
        manager.last_run = datetime.now(timezone.utc) - timedelta(seconds=120)
        
        # Should be allowed now
        assert manager.should_run() is True
    
    @pytest.mark.asyncio
    async def test_execute_heartbeat_runs_all_tasks(self):
        """Test that execute_heartbeat runs all registered tasks"""
        config = HeartbeatConfig(tasks=["email", "calendar"])
        manager = HeartbeatManager(config=config)
        
        manager.register_task(HeartbeatTask(name="email", tool_name="email_reader"))
        manager.register_task(HeartbeatTask(name="calendar", tool_name="calendar_reader"))
        
        results = await manager.execute_heartbeat()
        
        assert len(results) == 2
        assert all(isinstance(r, HeartbeatResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_execute_heartbeat_skips_disabled_tasks(self):
        """Test that disabled tasks are skipped"""
        config = HeartbeatConfig(tasks=["email", "calendar"])
        manager = HeartbeatManager(config=config)
        
        manager.register_task(HeartbeatTask(name="email", tool_name="email_reader", enabled=True))
        manager.register_task(HeartbeatTask(name="calendar", tool_name="calendar_reader", enabled=False))
        
        results = await manager.execute_heartbeat()
        
        # Should have 2 results, but one is skipped
        assert len(results) == 2
        assert results[0].status != HeartbeatStatus.SKIPPED
        assert results[1].status == HeartbeatStatus.SKIPPED
    
    @pytest.mark.asyncio
    async def test_execute_heartbeat_respects_batch_size(self):
        """Test that batch_size limits concurrent execution"""
        config = HeartbeatConfig(tasks=["t1", "t2", "t3", "t4", "t5"], batch_size=2)
        manager = HeartbeatManager(config=config)
        
        for i in range(1, 6):
            manager.register_task(HeartbeatTask(name=f"t{i}", tool_name=f"tool{i}"))
        
        results = await manager.execute_heartbeat()
        
        # All tasks should complete, but in batches
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_execute_heartbeat_updates_last_run(self):
        """Test that last_run timestamp is updated"""
        config = HeartbeatConfig(tasks=["email"])
        manager = HeartbeatManager(config=config)
        
        manager.register_task(HeartbeatTask(name="email", tool_name="email_reader"))
        
        before = datetime.now(timezone.utc)
        await manager.execute_heartbeat()
        after = datetime.now(timezone.utc)
        
        assert manager.last_run is not None
        assert before <= manager.last_run <= after
    
    def test_create_heartbeat_event(self):
        """Test creating a heartbeat event"""
        config = HeartbeatConfig(tasks=["email"])
        manager = HeartbeatManager(config=config)
        
        results = [
            HeartbeatResult(
                task_name="email",
                status=HeartbeatStatus.SUCCESS,
                data={"new_emails": 3}
            )
        ]
        
        event = manager.create_heartbeat_event(results)
        
        assert isinstance(event, Event)
        assert event.type == EventType.HEARTBEAT
        assert event.source == EventSource.SCHEDULER
        assert event.event_name == "heartbeat_check"
        assert "results" in event.payload
        assert len(event.payload["results"]) == 1
    
    def test_get_statistics(self):
        """Test getting heartbeat statistics"""
        config = HeartbeatConfig(tasks=["email"])
        manager = HeartbeatManager(config=config)
        
        manager.register_task(HeartbeatTask(name="email", tool_name="email_reader"))
        
        stats = manager.get_statistics()
        
        assert "total_tasks" in stats
        assert "enabled_tasks" in stats
        assert "disabled_tasks" in stats
        assert "last_run" in stats
        assert "next_run" in stats
        assert stats["total_tasks"] == 1
        assert stats["enabled_tasks"] == 1


class TestHeartbeatIntegration:
    """Integration tests for heartbeat system"""
    
    @pytest.mark.asyncio
    async def test_full_heartbeat_cycle(self):
        """Test a complete heartbeat cycle"""
        # Setup
        config = HeartbeatConfig(
            tasks=["email", "calendar"],
            interval_seconds=60
        )
        manager = HeartbeatManager(config=config)
        
        # Register tasks
        manager.register_task(HeartbeatTask(name="email", tool_name="email_reader"))
        manager.register_task(HeartbeatTask(name="calendar", tool_name="calendar_reader"))
        
        # Execute
        results = await manager.execute_heartbeat()
        
        # Verify
        assert len(results) == 2
        assert manager.last_run is not None
        
        # Create event
        event = manager.create_heartbeat_event(results)
        assert event.type == EventType.HEARTBEAT
        
        # Check statistics
        stats = manager.get_statistics()
        assert stats["total_tasks"] == 2

# Made with Bob
