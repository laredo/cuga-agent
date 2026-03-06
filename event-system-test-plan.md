# CUGA Event System Test Plan

**Version:** 2.0
**Date:** 2026-03-06
**Purpose:** Comprehensive testing strategy for event-driven enablement with OpenClaw patterns

**Updates:**
- Added Heartbeat system tests
- Added session management tests (main vs isolated)
- Added Human-in-the-Loop approval tests
- Added checkpoint/resume mechanism tests

---

## Test Strategy Overview

This test plan covers:
1. **Unit Tests** - Individual component testing
2. **Integration Tests** - End-to-end workflow testing
3. **Performance Tests** - Load and stress testing
4. **Security Tests** - Authentication and authorization
5. **Reliability Tests** - Retry logic and error handling
6. **Heartbeat Tests** - Batched monitoring functionality
7. **Session Management Tests** - Main vs isolated session routing
8. **Approval Tests** - Human-in-the-loop approval workflows

---

## 1. Unit Tests

### 1.1 Event Model Tests

**File:** `tests/unit/test_event_models.py`

```python
import pytest
from datetime import datetime
from cuga.backend.events.models import Event, EventType, EventSource

class TestEventModel:
    """Test Event model creation and validation"""
    
    def test_event_creation_with_defaults(self):
        """Test creating event with default values"""
        event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="pull_request",
            payload={"action": "opened"}
        )
        
        assert event.id is not None
        assert event.status == "pending"
        assert event.retry_count == 0
        assert event.max_retries == 3
        assert isinstance(event.created_at, datetime)
        assert event.processed_at is None
    
    def test_event_creation_with_custom_values(self):
        """Test creating event with custom values"""
        event = Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="app_mention",
            payload={"text": "Hello"},
            metadata={"channel": "general"},
            status="processing",
            retry_count=1
        )
        
        assert event.type == EventType.SLACK
        assert event.metadata["channel"] == "general"
        assert event.status == "processing"
        assert event.retry_count == 1
    
    def test_event_serialization(self):
        """Test event can be serialized to dict"""
        event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="daily_summary",
            payload={"message": "Run summary"}
        )
        
        event_dict = event.dict()
        assert event_dict["type"] == "cron"
        assert event_dict["source"] == "scheduler"
        assert "id" in event_dict
    
    def test_event_validation(self):
        """Test event validation fails with invalid data"""
        with pytest.raises(ValueError):
            Event(
                type="invalid_type",
                source=EventSource.WEBHOOK,
                event_name="test",
                payload={}
            )
```

### 1.2 Event Queue Tests

**File:** `tests/unit/test_event_queue.py`

```python
import pytest
import asyncio
from cuga.backend.events.models import Event, EventType, EventSource, EventPriority

class TestEventQueue:
    """Test event queue operations"""
    
    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self):
        """Test basic enqueue and dequeue operations"""
        queue = EventQueue(backend="memory")
        
        event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="push",
            payload={}
        )
        
        await queue.enqueue(event)
        dequeued = await queue.dequeue()
        
        assert dequeued is not None
        assert dequeued.id == event.id
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test events are dequeued by priority"""
        queue = EventQueue(backend="memory")
        
        low_event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="low",
            payload={},
            priority=EventPriority.LOW
        )
        
        high_event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="high",
            payload={},
            priority=EventPriority.HIGH
        )
        
        await queue.enqueue(low_event)
        await queue.enqueue(high_event)
        
        first = await queue.dequeue()
        assert first.priority == EventPriority.HIGH
    
    @pytest.mark.asyncio
    async def test_empty_queue(self):
        """Test dequeue from empty queue returns None"""
        queue = EventQueue(backend="memory")
        result = await queue.dequeue()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_redis_backend(self):
        """Test Redis backend operations"""
        queue = EventQueue(backend="redis")
        
        event = Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="message",
            payload={}
        )
        
        await queue.enqueue(event)
        dequeued = await queue.dequeue()
        
        assert dequeued.id == event.id
```

### 1.3 Event Router Tests

**File:** `tests/unit/test_event_router.py`

```python
import pytest
from cuga.backend.events.router import EventRouter, EventRoute
from cuga.backend.events.models import Event, EventType, EventSource

class TestEventRouter:
    """Test event routing logic"""
    
    @pytest.mark.asyncio
    async def test_simple_route_matching(self):
        """Test basic route matching"""
        router = EventRouter()
        
        async def github_handler(event):
            return {"handled_by": "github"}
        
        router.add_route(
            pattern={"type": "github"},
            handler=github_handler
        )
        
        event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="push",
            payload={}
        )
        
        result = await router.route(event)
        assert result["handled_by"] == "github"
    
    @pytest.mark.asyncio
    async def test_specific_event_name_matching(self):
        """Test matching specific event names"""
        router = EventRouter()
        
        async def pr_handler(event):
            return {"handled": "pr"}
        
        async def issue_handler(event):
            return {"handled": "issue"}
        
        router.add_route(
            pattern={"type": "github", "event_name": "pull_request"},
            handler=pr_handler
        )
        
        router.add_route(
            pattern={"type": "github", "event_name": "issues"},
            handler=issue_handler
        )
        
        pr_event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="pull_request",
            payload={}
        )
        
        result = await router.route(pr_event)
        assert result["handled"] == "pr"
    
    @pytest.mark.asyncio
    async def test_priority_routing(self):
        """Test routes are matched by priority"""
        router = EventRouter()
        
        async def high_priority_handler(event):
            return {"priority": "high"}
        
        async def low_priority_handler(event):
            return {"priority": "low"}
        
        router.add_route(
            pattern={"type": "github"},
            handler=low_priority_handler,
            priority=1
        )
        
        router.add_route(
            pattern={"type": "github"},
            handler=high_priority_handler,
            priority=10
        )
        
        event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="push",
            payload={}
        )
        
        result = await router.route(event)
        assert result["priority"] == "high"
    
    @pytest.mark.asyncio
    async def test_no_matching_route(self):
        """Test error when no route matches"""
        router = EventRouter()
        
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="unknown",
            payload={}
        )
        
        with pytest.raises(ValueError, match="No route"):
            await router.route(event)
```

### 1.4 Cron Scheduler Tests

**File:** `tests/unit/test_cron_scheduler.py`

```python
import pytest
import asyncio
from datetime import datetime
from cuga.backend.events.scheduler import CronScheduler, CronJob
from cuga.backend.events.models import EventQueue

class TestCronScheduler:
    """Test cron job scheduling"""
    
    @pytest.mark.asyncio
    async def test_add_cron_job(self):
        """Test adding a cron job"""
        queue = EventQueue(backend="memory")
        scheduler = CronScheduler(queue, {})
        
        job = CronJob(
            name="test_job",
            schedule={"kind": "cron", "expr": {"hour": 9, "minute": 0}},
            payload={"message": "Test"}
        )
        
        job_id = scheduler.add_job(job)
        assert job_id in scheduler.jobs
        assert scheduler.jobs[job_id].name == "test_job"
    
    @pytest.mark.asyncio
    async def test_interval_job(self):
        """Test interval-based job"""
        queue = EventQueue(backend="memory")
        scheduler = CronScheduler(queue, {})
        
        job = CronJob(
            name="interval_job",
            schedule={"kind": "interval", "seconds": 60},
            payload={"message": "Every minute"}
        )
        
        scheduler.add_job(job)
        assert job.id in scheduler.jobs
    
    @pytest.mark.asyncio
    async def test_job_execution_creates_event(self):
        """Test job execution creates event in queue"""
        queue = EventQueue(backend="memory")
        scheduler = CronScheduler(queue, {})
        
        job = CronJob(
            name="test_job",
            schedule={"kind": "interval", "seconds": 1},
            payload={"message": "Test"}
        )
        
        scheduler.add_job(job)
        scheduler.start()
        
        # Wait for job to execute
        await asyncio.sleep(2)
        
        event = await queue.dequeue()
        assert event is not None
        assert event.type == EventType.CRON
        assert "test_job" in event.event_name
        
        scheduler.shutdown()
    
    def test_remove_job(self):
        """Test removing a job"""
        queue = EventQueue(backend="memory")
        scheduler = CronScheduler(queue, {})
        
        job = CronJob(
            name="test_job",
            schedule={"kind": "cron", "expr": {"hour": 9}},
            payload={}
        )
        
        job_id = scheduler.add_job(job)
        assert job_id in scheduler.jobs
        
        scheduler.remove_job(job_id)
        assert job_id not in scheduler.jobs

### 1.5 Heartbeat Manager Tests

**File:** `tests/unit/test_heartbeat.py`

```python
import pytest
import asyncio
from cuga.backend.events.heartbeat import HeartbeatManager, HeartbeatConfig
from cuga.backend.events.models import EventQueue, EventType

class TestHeartbeatManager:
    """Test heartbeat functionality"""
    
    @pytest.mark.asyncio
    async def test_heartbeat_creation(self):
        """Test creating heartbeat configuration"""
        config = HeartbeatConfig(
            enabled=True,
            interval_seconds=1800,
            tasks=["email", "calendar", "slack"],
            thread_id="main"
        )
        
        assert config.enabled is True
        assert config.interval_seconds == 1800
        assert len(config.tasks) == 3
        assert config.thread_id == "main"
    
    @pytest.mark.asyncio
    async def test_heartbeat_execution(self):
        """Test heartbeat executes and creates batched event"""
        queue = EventQueue(backend="memory")
        config = HeartbeatConfig(
            enabled=True,
            interval_seconds=1,  # 1 second for testing
            tasks=["email", "calendar"],
            thread_id="main"
        )
        
        manager = HeartbeatManager(queue, config)
        manager.start()
        
        # Wait for heartbeat to execute
        await asyncio.sleep(2)
        
        event = await queue.dequeue()
        assert event is not None
        assert event.type == EventType.HEARTBEAT
        assert event.payload["session_target"] == "main"
        assert event.payload["thread_id"] == "main"
        assert len(event.payload["tasks"]) == 2
        assert event.metadata["batched"] is True
        
        manager.scheduler.shutdown()
    
    @pytest.mark.asyncio
    async def test_heartbeat_disabled(self):
        """Test heartbeat doesn't execute when disabled"""
        queue = EventQueue(backend="memory")
        config = HeartbeatConfig(
            enabled=False,
            interval_seconds=1,
            tasks=["email"]
        )
        
        manager = HeartbeatManager(queue, config)
        manager.start()
        
        await asyncio.sleep(2)
        
        event = await queue.dequeue()
        assert event is None  # No event should be created
    
    @pytest.mark.asyncio
    async def test_heartbeat_batched_message(self):
        """Test heartbeat creates proper batched message"""
        queue = EventQueue(backend="memory")
        config = HeartbeatConfig(
            enabled=True,
            interval_seconds=1,
            tasks=["email", "calendar", "slack"],
            thread_id="user-123"
        )
        
        manager = HeartbeatManager(queue, config)
        await manager._execute_heartbeat()
        
        event = await queue.dequeue()
        message = event.payload["message"]
        
        assert "Periodic status check" in message
        assert "email" in message.lower()
        assert "calendar" in message.lower()
        assert "slack" in message.lower()
        assert event.payload["thread_id"] == "user-123"
```

### 1.6 Session Management Tests

**File:** `tests/unit/test_session_management.py`

```python
import pytest
from cuga.backend.events.scheduler import CronJob
from cuga.backend.events.models import Event, EventType

class TestSessionManagement:
    """Test session routing and management"""
    
    def test_cron_job_isolated_session(self):
        """Test cron job defaults to isolated session"""
        job = CronJob(
            name="test_job",
            schedule={"kind": "cron", "expr": {"hour": 9}},
            payload={"message": "Test"}
        )
        
        assert job.session_target == "isolated"
        assert job.thread_id is None
    
    def test_cron_job_main_session(self):
        """Test cron job with main session"""
        job = CronJob(
            name="reminder",
            schedule={"kind": "interval", "seconds": 1200},
            payload={"message": "Meeting reminder"},
            session_target="main",
            thread_id="user-123"
        )
        
        assert job.session_target == "main"
        assert job.thread_id == "user-123"
    
    def test_wake_mode_configuration(self):
        """Test wake mode settings"""
        job = CronJob(
            name="test_job",
            schedule={"kind": "cron", "expr": {"hour": 9}},
            payload={"message": "Test"},
            wake_mode="next-heartbeat"
        )
        
        assert job.wake_mode == "next-heartbeat"
    
    @pytest.mark.asyncio
    async def test_session_routing_in_handler(self):
        """Test event handler routes to correct session"""
        from cuga.backend.events.handlers import EventHandlers
        
        # Mock agent graph
        mock_graph = MockAgentGraph()
        handlers = EventHandlers(mock_graph, {})
        
        # Test isolated session
        event_isolated = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="cron:test",
            payload={
                "job_id": "job-123",
                "message": "Test",
                "session_target": "isolated"
            }
        )
        
        await handlers.handle_cron_job(event_isolated)
        assert mock_graph.last_session_key == "cron:job-123"
        
        # Test main session
        event_main = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="cron:reminder",
            payload={
                "job_id": "job-456",
                "message": "Reminder",
                "session_target": "main",
                "thread_id": "user-789"
            }
        )
        
        await handlers.handle_cron_job(event_main)
        assert mock_graph.last_session_key == "user-789"
```

### 1.7 Approval System Tests

**File:** `tests/unit/test_approval.py`

```python
import pytest
from datetime import datetime, timedelta
from cuga.backend.events.approval import ApprovalManager, ApprovalRequest

class TestApprovalSystem:
    """Test human-in-the-loop approval system"""
    
    @pytest.mark.asyncio
    async def test_approval_request_creation(self):
        """Test creating approval request"""
        storage = MockApprovalStorage()
        manager = ApprovalManager(storage)
        
        token = await manager.request_approval(
            event_id="event-123",
            thread_id="thread-456",
            action={"type": "deploy", "description": "Deploy to production"},
            risk_level="high",
            timeout_hours=24
        )
        
        assert token is not None
        approval = await storage.get(token)
        assert approval.status == "pending"
        assert approval.risk_level == "high"
        assert approval.event_id == "event-123"
    
    @pytest.mark.asyncio
    async def test_approval_approve(self):
        """Test approving an action"""
        storage = MockApprovalStorage()
        manager = ApprovalManager(storage)
        
        token = await manager.request_approval(
            event_id="event-123",
            thread_id="thread-456",
            action={"type": "deploy"},
            risk_level="high"
        )
        
        success = await manager.approve(token, "alice@example.com")
        assert success is True
        
        approval = await storage.get(token)
        assert approval.status == "approved"
        assert approval.approved_by == "alice@example.com"
        assert approval.approved_at is not None
    
    @pytest.mark.asyncio
    async def test_approval_reject(self):
        """Test rejecting an action"""
        storage = MockApprovalStorage()
        manager = ApprovalManager(storage)
        
        token = await manager.request_approval(
            event_id="event-123",
            thread_id="thread-456",
            action={"type": "delete"},
            risk_level="critical"
        )
        
        success = await manager.reject(token, "bob@example.com", "Too risky")
        assert success is True
        
        approval = await storage.get(token)
        assert approval.status == "rejected"
        assert approval.approved_by == "bob@example.com"
    
    @pytest.mark.asyncio
    async def test_approval_expiration(self):
        """Test approval expires after timeout"""
        storage = MockApprovalStorage()
        manager = ApprovalManager(storage)
        
        # Create approval that expires in 1 second
        approval = ApprovalRequest(
            token="test-token",
            event_id="event-123",
            thread_id="thread-456",
            action={"type": "deploy"},
            risk_level="high",
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=1)
        )
        await storage.save(approval)
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Check approval status
        result = await manager.check_approval("test-token")
        assert result.status == "expired"
    
    @pytest.mark.asyncio
    async def test_approval_cannot_approve_twice(self):
        """Test cannot approve already processed request"""
        storage = MockApprovalStorage()
        manager = ApprovalManager(storage)
        
        token = await manager.request_approval(
            event_id="event-123",
            thread_id="thread-456",
            action={"type": "deploy"},
            risk_level="high"
        )
        
        # First approval succeeds
        success1 = await manager.approve(token, "alice@example.com")
        assert success1 is True
        
        # Second approval fails
        success2 = await manager.approve(token, "bob@example.com")
        assert success2 is False
```

```

---

## 2. Integration Tests

### 2.1 GitHub Webhook Flow

**File:** `tests/integration/test_github_webhook.py`

```python
import pytest
import hmac
import hashlib
from fastapi.testclient import TestClient
from cuga.backend.events.server import EventServer

class TestGitHubWebhook:
    """Test GitHub webhook integration"""
    
    @pytest.fixture
    def client(self):
        config = {"webhooks": {"github": {"secret": "test_secret"}}}
        server = EventServer(config)
        return TestClient(server.app)
    
    def test_github_pr_opened(self, client):
        """Test GitHub PR opened webhook"""
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 123,
                "title": "Test PR",
                "user": {"login": "testuser"},
                "html_url": "https://github.com/test/repo/pull/123"
            },
            "repository": {
                "full_name": "test/repo"
            }
        }
        
        # Create signature
        secret = b"test_secret"
        signature = hmac.new(
            secret,
            msg=json.dumps(payload).encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        response = client.post(
            "/webhooks/github",
            json=payload,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": f"sha256={signature}"
            }
        )
        
        assert response.status_code == 200
        assert "event_id" in response.json()
    
    def test_github_invalid_signature(self, client):
        """Test GitHub webhook with invalid signature"""
        payload = {"action": "opened"}
        
        response = client.post(
            "/webhooks/github",
            json=payload,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=invalid"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_github_pr_end_to_end(self):
        """Test complete GitHub PR workflow"""
        # Setup
        config = {"webhooks": {"github": {"secret": "test_secret"}}}
        manager = EventManager(config)
        
        # Start manager
        asyncio.create_task(manager.start())
        await asyncio.sleep(1)
        
        # Send webhook
        client = TestClient(manager.event_server.app)
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 123,
                "title": "Test PR",
                "user": {"login": "testuser"},
                "html_url": "https://github.com/test/repo/pull/123"
            }
        }
        
        response = client.post("/webhooks/github", json=payload)
        assert response.status_code == 200
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Check event was processed
        events = manager.event_store.get_recent_events(limit=1)
        assert len(events) == 1
        assert events[0].status == "completed"
```

### 2.2 Slack Integration Flow

**File:** `tests/integration/test_slack_webhook.py`

```python
import pytest
import hmac
import hashlib
import time
from fastapi.testclient import TestClient

class TestSlackWebhook:
    """Test Slack webhook integration"""
    
    @pytest.fixture
    def client(self):
        config = {
            "webhooks": {
                "slack": {
                    "signing_secret": "test_secret",
                    "bot_token": "xoxb-test"
                }
            }
        }
        server = EventServer(config)
        return TestClient(server.app)
    
    def test_slack_url_verification(self, client):
        """Test Slack URL verification challenge"""
        payload = {
            "type": "url_verification",
            "challenge": "test_challenge_123"
        }
        
        response = client.post("/webhooks/slack", json=payload)
        
        assert response.status_code == 200
        assert response.json()["challenge"] == "test_challenge_123"
    
    def test_slack_app_mention(self, client):
        """Test Slack app mention event"""
        timestamp = str(int(time.time()))
        payload = {
            "type": "event_callback",
            "event": {
                "type": "app_mention",
                "text": "<@BOT> help me",
                "user": "U123",
                "channel": "C123",
                "ts": "1234567890.123456"
            }
        }
        
        # Create signature
        sig_basestring = f"v0:{timestamp}:{json.dumps(payload)}"
        signature = hmac.new(
            b"test_secret",
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        response = client.post(
            "/webhooks/slack",
            json=payload,
            headers={
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": f"v0={signature}"
            }
        )
        
        assert response.status_code == 200
        assert "event_id" in response.json()
    
    @pytest.mark.asyncio
    async def test_slack_mention_end_to_end(self, mock_slack_api):
        """Test complete Slack mention workflow"""
        manager = EventManager(config)
        asyncio.create_task(manager.start())
        await asyncio.sleep(1)
        
        # Send mention event
        client = TestClient(manager.event_server.app)
        payload = {
            "type": "event_callback",
            "event": {
                "type": "app_mention",
                "text": "<@BOT> What's the weather?",
                "channel": "C123",
                "ts": "1234567890.123456"
            }
        }
        
        response = client.post("/webhooks/slack", json=payload)
        assert response.status_code == 200
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Verify Slack API was called to post response
        assert mock_slack_api.post_message_called

### 2.4 Heartbeat Integration Tests

**File:** `tests/integration/test_heartbeat_integration.py`

```python
import pytest
import asyncio
from cuga.backend.events.manager import EventManager

class TestHeartbeatIntegration:
    """Test heartbeat end-to-end integration"""
    
    @pytest.mark.asyncio
    async def test_heartbeat_execution_flow(self):
        """Test complete heartbeat execution flow"""
        config = {
            "heartbeat": {
                "enabled": True,
                "interval_seconds": 1,
                "tasks": ["email", "calendar"],
                "thread_id": "main"
            }
        }
        
        manager = EventManager(config)
        asyncio.create_task(manager._process_events())
        manager.heartbeat_manager.start()
        
        # Wait for heartbeat to execute
        await asyncio.sleep(2)
        
        # Check event was created and processed
        events = manager.event_store.get_events_by_type(EventType.HEARTBEAT)
        assert len(events) > 0
        assert events[0].status == "completed"
        assert events[0].payload["session_target"] == "main"
        
        manager.heartbeat_manager.scheduler.shutdown()
    
    @pytest.mark.asyncio
    async def test_heartbeat_vs_multiple_cron_efficiency(self):
        """Test heartbeat is more efficient than multiple cron jobs"""
        # Setup: 4 separate cron jobs
        cron_config = {"cron": {"enabled": True}}
        cron_manager = EventManager(cron_config)
        
        for task in ["email", "calendar", "slack", "github"]:
            job = CronJob(
                name=f"check_{task}",
                schedule={"kind": "interval", "seconds": 1},
                payload={"message": f"Check {task}"},
                session_target="isolated"
            )
            cron_manager.cron_scheduler.add_job(job)
        
        # Setup: 1 heartbeat
        heartbeat_config = {
            "heartbeat": {
                "enabled": True,
                "interval_seconds": 1,
                "tasks": ["email", "calendar", "slack", "github"],
                "thread_id": "main"
            }
        }
        heartbeat_manager = EventManager(heartbeat_config)
        
        # Run both for 3 seconds
        cron_manager.cron_scheduler.start()
        heartbeat_manager.heartbeat_manager.start()
        
        asyncio.create_task(cron_manager._process_events())
        asyncio.create_task(heartbeat_manager._process_events())
        
        await asyncio.sleep(3)
        
        # Count events
        cron_events = cron_manager.event_store.get_events_by_type(EventType.CRON)
        heartbeat_events = heartbeat_manager.event_store.get_events_by_type(EventType.HEARTBEAT)
        
        # Cron should create ~12 events (4 jobs * 3 seconds)
        # Heartbeat should create ~3 events (1 per second)
        assert len(cron_events) >= 10
        assert len(heartbeat_events) <= 4
        assert len(heartbeat_events) < len(cron_events) / 3
        
        cron_manager.cron_scheduler.shutdown()
        heartbeat_manager.heartbeat_manager.scheduler.shutdown()

### 2.5 Session Management Integration Tests

**File:** `tests/integration/test_session_management.py`

```python
import pytest
import asyncio

class TestSessionManagementIntegration:
    """Test session routing in real scenarios"""
    
    @pytest.mark.asyncio
    async def test_isolated_session_no_context_pollution(self):
        """Test isolated session doesn't pollute main conversation"""
        manager = EventManager(config)
        asyncio.create_task(manager._process_events())
        
        # Create main conversation context
        main_event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="user_message",
            payload={
                "message": "Remember my name is Alice",
                "session_target": "main",
                "thread_id": "user-123"
            }
        )
        await manager.event_queue.enqueue(main_event)
        await asyncio.sleep(1)
        
        # Create isolated cron job
        cron_event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="cron:daily_report",
            payload={
                "job_id": "job-456",
                "message": "Generate daily report",
                "session_target": "isolated"
            }
        )
        await manager.event_queue.enqueue(cron_event)
        await asyncio.sleep(1)
        
        # Ask main session about name
        query_event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="user_message",
            payload={
                "message": "What's my name?",
                "session_target": "main",
                "thread_id": "user-123"
            }
        )
        await manager.event_queue.enqueue(query_event)
        await asyncio.sleep(1)
        
        # Main session should remember Alice
        # Isolated session should have no knowledge of Alice
        events = manager.event_store.get_events_by_thread("user-123")
        assert len(events) == 2  # Only main session events
    
    @pytest.mark.asyncio
    async def test_main_session_reminder_with_context(self):
        """Test reminder in main session has conversation context"""
        manager = EventManager(config)
        asyncio.create_task(manager._process_events())
        
        # User sets context
        context_event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="user_message",
            payload={
                "message": "I'm working on the authentication feature",
                "session_target": "main",
                "thread_id": "user-789"
            }
        )
        await manager.event_queue.enqueue(context_event)
        await asyncio.sleep(1)
        
        # Cron reminder in main session
        reminder_event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name="cron:reminder",
            payload={
                "job_id": "reminder-123",
                "message": "Time to commit your work",
                "session_target": "main",
                "thread_id": "user-789"
            }
        )
        await manager.event_queue.enqueue(reminder_event)
        await asyncio.sleep(1)
        
        # Agent should have context about authentication feature
        events = manager.event_store.get_events_by_thread("user-789")
        assert len(events) == 2
        assert events[1].payload["session_target"] == "main"

### 2.6 Approval Workflow Integration Tests

**File:** `tests/integration/test_approval_workflow.py`

```python
import pytest
import asyncio
from datetime import datetime, timedelta

class TestApprovalWorkflow:
    """Test complete approval workflows"""
    
    @pytest.mark.asyncio
    async def test_high_risk_action_requires_approval(self):
        """Test high-risk action triggers approval flow"""
        manager = EventManager(config)
        asyncio.create_task(manager._process_events())
        
        # GitHub PR merge event (high risk - triggers deployment)
        pr_event = Event(
            type=EventType.GITHUB,
            source=EventSource.WEBHOOK,
            event_name="pull_request",
            payload={
                "action": "closed",
                "pull_request": {
                    "merged": True,
                    "number": 123,
                    "base": {"ref": "main"}  # Merge to main = high risk
                }
            }
        )
        
        await manager.event_queue.enqueue(pr_event)
        await asyncio.sleep(2)
        
        # Check approval was requested
        approvals = manager.approval_manager.storage.get_pending()
        assert len(approvals) == 1
        assert approvals[0].risk_level == "high"
        assert approvals[0].action["type"] == "deploy"
    
    @pytest.mark.asyncio
    async def test_approval_and_resume_execution(self, mock_slack_api):
        """Test execution resumes after approval"""
        manager = EventManager(config)
        asyncio.create_task(manager._process_events())
        
        # Trigger high-risk action
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="deploy_request",
            payload={
                "action": "deploy_production",
                "service": "api-server"
            }
        )
        
        await manager.event_queue.enqueue(event)
        await asyncio.sleep(1)
        
        # Get approval token
        approvals = manager.approval_manager.storage.get_pending()
        token = approvals[0].token
        
        # Verify notification was sent
        assert mock_slack_api.post_message_called
        
        # Approve the action
        await manager.approval_manager.approve(token, "admin@example.com")
        
        # Wait for execution to resume
        await asyncio.sleep(2)
        
        # Check execution completed
        approval = await manager.approval_manager.storage.get(token)
        assert approval.status == "approved"
        
        # Check deployment actually happened
        events = manager.event_store.get_events_by_id(event.id)
        assert events[0].status == "completed"
    
    @pytest.mark.asyncio
    async def test_approval_rejection_stops_execution(self):
        """Test rejected approval stops execution"""
        manager = EventManager(config)
        asyncio.create_task(manager._process_events())
        
        # Trigger critical action
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="delete_database",
            payload={"database": "production"}
        )
        
        await manager.event_queue.enqueue(event)
        await asyncio.sleep(1)
        
        # Get approval token
        approvals = manager.approval_manager.storage.get_pending()
        token = approvals[0].token
        
        # Reject the action
        await manager.approval_manager.reject(
            token,
            "admin@example.com",
            "Too dangerous without backup"
        )
        
        await asyncio.sleep(1)
        
        # Check execution was stopped
        approval = await manager.approval_manager.storage.get(token)
        assert approval.status == "rejected"
        
        # Database should NOT be deleted
        events = manager.event_store.get_events_by_id(event.id)
        assert events[0].metadata.get("action_taken") != "database_deleted"
    
    @pytest.mark.asyncio
    async def test_approval_timeout_expires(self):
        """Test approval expires after timeout"""
        manager = EventManager(config)
        
        # Create approval with 1 second timeout
        token = await manager.approval_manager.request_approval(
            event_id="event-123",
            thread_id="thread-456",
            action={"type": "deploy"},
            risk_level="high",
            timeout_hours=0.0003  # ~1 second
        )
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Check approval
        approval = await manager.approval_manager.check_approval(token)
        assert approval.status == "expired"
        
        # Try to approve expired request
        success = await manager.approval_manager.approve(token, "admin@example.com")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_multi_channel_approval_notification(self, mock_slack_api, mock_email):
        """Test approval notifications sent to multiple channels"""
        manager = EventManager(config)
        
        token = await manager.approval_manager.request_approval(
            event_id="event-123",
            thread_id="thread-456",
            action={"type": "deploy", "description": "Deploy to production"},
            risk_level="critical"
        )
        
        await asyncio.sleep(1)
        
        # Check Slack notification
        assert mock_slack_api.post_message_called
        assert "Approval Required" in mock_slack_api.last_message
        assert token[:8] in mock_slack_api.last_message
        
        # Check email notification
        assert mock_email.send_called
        assert "Approval Required" in mock_email.last_subject
```

        assert mock_slack_api.last_channel == "C123"
```

### 2.3 Cron Job Execution

**File:** `tests/integration/test_cron_execution.py`

```python
import pytest
import asyncio
from datetime import datetime

class TestCronExecution:
    """Test cron job execution flow"""
    
    @pytest.mark.asyncio
    async def test_cron_job_creates_event(self):
        """Test cron job creates and processes event"""
        manager = EventManager(config)
        
        # Add cron job
        job = CronJob(
            name="test_job",
            schedule={"kind": "interval", "seconds": 1},
            payload={"message": "Test cron job"}
        )
        
        manager.cron_scheduler.add_job(job)
        manager.cron_scheduler.start()
        
        # Start event processing
        asyncio.create_task(manager._process_events())
        
        # Wait for job to execute
        await asyncio.sleep(2)
        
        # Check event was created and processed
        events = manager.event_store.get_events_by_type(EventType.CRON)
        assert len(events) > 0
        assert events[0].status == "completed"
    
    @pytest.mark.asyncio
    async def test_cron_job_with_delivery(self, mock_slack_api):
        """Test cron job with Slack delivery"""
        manager = EventManager(config)
        
        job = CronJob(
            name="daily_summary",
            schedule={"kind": "interval", "seconds": 1},
            payload={"message": "Generate daily summary"},
            delivery={
                "mode": "announce",
                "channel": "slack",
                "to": "#updates"
            }
        )
        
        manager.cron_scheduler.add_job(job)
        manager.cron_scheduler.start()
        asyncio.create_task(manager._process_events())
        
        await asyncio.sleep(3)
        
        # Verify delivery was made
        assert mock_slack_api.post_message_called
        assert mock_slack_api.last_channel == "#updates"
```

---

## 3. Performance Tests

### 3.1 Load Testing

**File:** `tests/performance/test_load.py`

```python
import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor

class TestEventSystemLoad:
    """Test event system under load"""
    
    @pytest.mark.asyncio
    async def test_high_volume_events(self):
        """Test processing 1000 events"""
        manager = EventManager(config)
        asyncio.create_task(manager._process_events())
        
        # Create 1000 events
        events = []
        for i in range(1000):
            event = Event(
                type=EventType.CUSTOM,
                source=EventSource.WEBHOOK,
                event_name=f"test_{i}",
                payload={"index": i}
            )
            events.append(event)
        
        # Enqueue all events
        start_time = time.time()
        for event in events:
            await manager.event_queue.enqueue(event)
        
        # Wait for processing
        while manager.event_queue.size() > 0:
            await asyncio.sleep(0.1)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Check all events processed
        processed = manager.event_store.get_events_by_status("completed")
        assert len(processed) == 1000
        
        # Check throughput
        throughput = 1000 / duration
        assert throughput > 100  # At least 100 events/sec
    
    @pytest.mark.asyncio
    async def test_concurrent_webhooks(self):
        """Test concurrent webhook requests"""
        client = TestClient(manager.event_server.app)
        
        async def send_webhook(i):
            payload = {"index": i}
            response = client.post("/webhooks/custom/test", json=payload)
            return response.status_code
        
        # Send 100 concurrent requests
        tasks = [send_webhook(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(status == 200 for status in results)
```

---

## 4. Security Tests

### 4.1 Authentication Tests

**File:** `tests/security/test_authentication.py`

```python
import pytest

class TestWebhookSecurity:
    """Test webhook security"""
    
    def test_github_signature_verification(self, client):
        """Test GitHub signature is verified"""
        payload = {"action": "opened"}
        
        # No signature
        response = client.post(
            "/webhooks/github",
            json=payload,
            headers={"X-GitHub-Event": "push"}
        )
        assert response.status_code == 401
        
        # Invalid signature
        response = client.post(
            "/webhooks/github",
            json=payload,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=invalid"
            }
        )
        assert response.status_code == 401
    
    def test_slack_signature_verification(self, client):
        """Test Slack signature is verified"""
        payload = {"type": "event_callback"}
        
        # No signature
        response = client.post("/webhooks/slack", json=payload)
        assert response.status_code == 401
        
        # Invalid signature
        response = client.post(
            "/webhooks/slack",
            json=payload,
            headers={
                "X-Slack-Request-Timestamp": "123456",
                "X-Slack-Signature": "v0=invalid"
            }
        )
        assert response.status_code == 401
    
    def test_custom_webhook_token(self, client):
        """Test custom webhook requires token"""
        payload = {"data": "test"}
        
        # No token
        response = client.post("/webhooks/custom/test", json=payload)
        assert response.status_code == 401
        
        # Invalid token
        response = client.post(
            "/webhooks/custom/test",
            json=payload,
            headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401
```

### 4.2 Rate Limiting Tests

**File:** `tests/security/test_rate_limiting.py`

```python
import pytest

class TestRateLimiting:
    """Test rate limiting"""
    
    @pytest.mark.asyncio
    async def test_event_rate_limiting(self):
        """Test events are rate limited"""
        policy = EventPolicy(
            event_types=["github"],
            rate_limit={"requests": 10, "window": "1m"}
        )
        
        enforcer = EventPolicyEnforcer(policy_system)
        
        # Send 15 events
        for i in range(15):
            event = Event(
                type=EventType.GITHUB,
                source=EventSource.WEBHOOK,
                event_name="push",
                payload={}
            )
            
            allowed, reason = await enforcer.check_event(event)
            
            if i < 10:
                assert allowed is True
            else:
                assert allowed is False
                assert "Rate limit" in reason
```

---

## 5. Reliability Tests

### 5.1 Retry Logic Tests

**File:** `tests/reliability/test_retry.py`

```python
import pytest

class TestRetryLogic:
    """Test event retry logic"""
    
    @pytest.mark.asyncio
    async def test_failed_event_retries(self):
        """Test failed events are retried"""
        manager = EventManager(config)
        
        # Create handler that fails first 2 times
        call_count = 0
        async def failing_handler(event):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return {"success": True}
        
        manager.event_router.add_route(
            {"type": "custom"},
            failing_handler
        )
        
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={}
        )
        
        await manager.event_queue.enqueue(event)
        asyncio.create_task(manager._process_events())
        
        # Wait for retries
        await asyncio.sleep(10)
        
        # Check event eventually succeeded
        stored_event = manager.event_store.get_event(event.id)
        assert stored_event.status == "completed"
        assert stored_event.retry_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test event fails after max retries"""
        manager = EventManager(config)
        
        async def always_failing_handler(event):
            raise Exception("Always fails")
        
        manager.event_router.add_route(
            {"type": "custom"},
            always_failing_handler
        )
        
        event = Event(
            type=EventType.CUSTOM,
            source=EventSource.WEBHOOK,
            event_name="test",
            payload={},
            max_retries=3
        )
        
        await manager.event_queue.enqueue(event)
        asyncio.create_task(manager._process_events())
        
        await asyncio.sleep(15)
        
        stored_event = manager.event_store.get_event(event.id)
        assert stored_event.status == "failed"
        assert stored_event.retry_count == 3
```

---

## 6. Test Fixtures and Mocks

### 6.1 Common Fixtures

**File:** `tests/conftest.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def event_config():
    """Standard event configuration with all features"""
    return {
        "events": {
            "enabled": True,
            "http_port": 8002,
            "webhooks": {
                "github": {"secret": "test_secret"},
                "slack": {
                    "signing_secret": "test_secret",
                    "bot_token": "xoxb-test"
                }
            },
            "heartbeat": {
                "enabled": True,
                "interval_seconds": 1800,
                "tasks": ["email", "calendar"],
                "thread_id": "main"
            },
            "approval": {
                "enabled": True,
                "default_timeout_hours": 24,
                "notification_channels": ["slack", "email"]
            }
        }
    }

@pytest.fixture
def mock_approval_storage():
    """Mock approval storage"""
    storage = Mock()
    storage.approvals = {}
    
    async def save(approval):
        storage.approvals[approval.token] = approval
    
    async def get(token):
        return storage.approvals.get(token)
    
    async def get_pending():
        return [a for a in storage.approvals.values() if a.status == "pending"]
    
    storage.save = save
    storage.get = get
    storage.get_pending = get_pending
    
    return storage

@pytest.fixture
def mock_agent_graph():
    """Mock agent graph for testing"""
    mock = Mock()
    mock.last_session_key = None
    mock.last_message = None
    
    async def ainvoke(state, config):
        mock.last_session_key = config["configurable"]["thread_id"]
        mock.last_message = state["messages"][0]["content"]
        return {"answer": "Mock response"}
    
    mock.graph = Mock()
    mock.graph.ainvoke = ainvoke
    
    return mock

**File:** `tests/conftest.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def event_config():
    """Standard event configuration"""
    return {
        "events": {
            "enabled": True,
            "http_port": 8002,
            "webhooks": {
                "github": {"secret": "test_secret"},
                "slack": {
                    "signing_secret": "test_secret",
                    "bot_token": "xoxb-test"
                }
            }
        }
    }

@pytest.fixture
def mock_slack_api():
    """Mock Slack API client"""
    mock = Mock()
    mock.post_message = AsyncMock(return_value={"ok": True})
    mock.post_message_called = False
    mock.last_channel = None
    
    async def track_post_message(channel, text, thread_ts=None):
        mock.post_message_called = True
        mock.last_channel = channel
        return {"ok": True}
    
    mock.post_message = track_post_message
    return mock

@pytest.fixture
def mock_github_api():
    """Mock GitHub API client"""
    mock = Mock()
    mock.create_comment = AsyncMock(return_value={"id": 123})
    return mock

@pytest.fixture
async def event_manager(event_config):
    """Event manager instance"""
    manager = EventManager(event_config)
    yield manager
    await manager.shutdown()
```

---

## 7. Test Execution

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/

# Run with coverage
pytest --cov=cuga.backend.events tests/

# Run specific test
pytest tests/unit/test_event_models.py::TestEventModel::test_event_creation

# Run with verbose output
pytest -v tests/

# Run performance tests only
pytest -m performance tests/
```

### Test Markers

```python
# In pytest.ini
[pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    security: Security tests
    reliability: Reliability tests
    heartbeat: Heartbeat system tests
    session: Session management tests
    approval: Approval workflow tests
    slow: Slow running tests
```

---

## 8. Continuous Integration

### GitHub Actions Workflow

**File:** `.github/workflows/test-events.yml`

```yaml
name: Event System Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis:7
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=cuga.backend.events
      
      - name: Run heartbeat tests
        run: pytest -m heartbeat tests/ -v
      
      - name: Run session management tests
        run: pytest -m session tests/ -v
      
      - name: Run approval tests
        run: pytest -m approval tests/ -v
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          GITHUB_WEBHOOK_SECRET: test_secret
          SLACK_SIGNING_SECRET: test_secret
      
      - name: Run security tests
        run: pytest tests/security/ -v
      
      - name: Generate coverage report
        run: pytest --cov=cuga.backend.events --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 9. Test Coverage Goals

### Coverage Targets

- **Overall Coverage:** >90%
- **Unit Tests:** >95%
- **Integration Tests:** >85%
- **Critical Paths:** 100%

### Critical Paths

1. Event creation and validation
2. Webhook signature verification
3. Event routing and handling
4. Retry logic
5. Policy enforcement
6. **Heartbeat execution and batching** (NEW)
7. **Session routing (main vs isolated)** (NEW)
8. **Approval request and resume** (NEW)

---

## 10. Manual Testing Checklist

### GitHub Integration

- [ ] PR opened triggers agent review
- [ ] PR comment triggers agent response
- [ ] Issue created triggers agent acknowledgment
- [ ] Push event triggers appropriate action
- [ ] Invalid signature is rejected
- [ ] Rate limiting works correctly

### Slack Integration

- [ ] App mention triggers agent response
- [ ] Message in thread maintains context
- [ ] URL verification challenge works
- [ ] Invalid signature is rejected
- [ ] Bot responds in correct channel

### Heartbeat System (NEW)

- [ ] Heartbeat executes at configured interval
- [ ] Multiple tasks batched into single execution
- [ ] Heartbeat runs in main session with context
- [ ] Heartbeat can be configured via CLI
- [ ] Heartbeat can be disabled
- [ ] Heartbeat more efficient than separate cron jobs

### Cron Jobs

- [ ] Daily job executes at correct time
- [ ] Interval job executes repeatedly
- [ ] Isolated session jobs don't pollute main context
- [ ] Main session jobs have conversation context
- [ ] Job results delivered to correct channel
- [ ] Failed jobs retry correctly
- [ ] Jobs can be added/removed via CLI
- [ ] Session targeting works correctly (--session flag)

### Approval Workflows (NEW)

- [ ] High-risk actions trigger approval request
- [ ] Approval notifications sent to multiple channels
- [ ] Approval can be granted via CLI
- [ ] Approval can be rejected via CLI
- [ ] Execution resumes after approval
- [ ] Execution stops after rejection
- [ ] Approvals expire after timeout
- [ ] Expired approvals cannot be approved
- [ ] Approval audit log is maintained

### System Health

- [ ] Metrics are collected correctly
- [ ] Dashboard shows accurate data
- [ ] Alerts trigger on failures
- [ ] Event store persists data
- [ ] Queue handles backpressure

---

## Summary

This comprehensive test plan ensures the event-driven system is:

1. **Functionally Correct** - All components work as designed
2. **Reliable** - Handles failures gracefully with retries
3. **Secure** - Properly authenticates and authorizes requests
4. **Performant** - Handles high load efficiently
5. **Observable** - Provides metrics and monitoring
6. **Context-Aware** - Heartbeat and session management work correctly
7. **Safe** - Human-in-the-loop approvals prevent dangerous actions

**New Test Coverage (v2.0):**
- **Heartbeat Tests**: 6 unit tests, 2 integration tests
- **Session Management Tests**: 4 unit tests, 2 integration tests
- **Approval Tests**: 6 unit tests, 6 integration tests
- **Total New Tests**: 26 additional test cases

**Test Execution Priority:**
1. Unit tests (fast feedback) - Including heartbeat, session, approval
2. Heartbeat tests (efficiency validation)
3. Session management tests (context isolation)
4. Approval tests (safety validation)
5. Integration tests (workflow validation)
6. Security tests (critical for production)
7. Performance tests (scalability validation)
8. Manual testing (user experience validation)

**Key Improvements:**
- Tests verify heartbeat is more efficient than multiple cron jobs
- Tests ensure session isolation prevents context pollution
- Tests validate approval workflow with checkpoint/resume
- Tests confirm multi-channel notifications work
- Tests verify approval timeouts and expiration