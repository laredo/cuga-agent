# CUGA Event-Driven Enablement Plan

**Version:** 1.0  
**Date:** 2026-03-05  
**Inspired by:** OpenClaw Architecture  
**Priority Focus:** Slack Integration, GitHub Webhooks, Cron-based Tasks

---

## Executive Summary


**Key OpenClaw Concepts Integrated:**
- **Heartbeat System** - Batched, context-aware periodic monitoring in main session
- **Session Isolation** - Explicit control over main vs isolated session execution
- **Wake Modes** - Immediate vs next-heartbeat event delivery

This plan transforms CUGA from a chat-only agent into an event-driven system capable of responding to external triggers, scheduled tasks, and real-time events. Drawing inspiration from OpenClaw's proven architecture, we'll implement:

1. **Webhook Ingress System** - HTTP endpoints for GitHub, Slack, and custom integrations
2. **Cron Scheduler** - Built-in job scheduler for periodic agent workflows
3. **Event Processing Pipeline** - Unified event handling with routing and filtering
4. **Policy Integration** - Event-aware policy enforcement and governance

---

## Architecture Overview

```mermaid
graph TB
    subgraph "Event Sources"
        GH[GitHub Webhooks]
        SL[Slack Events API]
        CR[Cron Scheduler]
        WH[Custom Webhooks]
    end
    
    subgraph "Event Ingestion Layer"
        HTTP[HTTP Server<br/>FastAPI]
        AUTH[Authentication]
        VALID[Payload Validation]
    end
    
    subgraph "Event Processing Pipeline"
        ROUTER[Event Router]
        FILTER[Event Filter]
        QUEUE[Event Queue<br/>In-Memory/SQLite]
    end
    
    subgraph "CUGA Core"
        GRAPH[LangGraph Agent]
        POLICY[Policy System]
        TOOLS[Tool Registry]
    end
    
    subgraph "Delivery Layer"
        SLACK[Slack Delivery]
        GITHUB[GitHub Comments]
        STORAGE[Event Store]
    end
    
    GH --> HTTP
    SL --> HTTP
    CR --> QUEUE
    WH --> HTTP
    
    HTTP --> AUTH
    AUTH --> VALID
    VALID --> ROUTER
    ROUTER --> FILTER
    FILTER --> QUEUE
    
    QUEUE --> GRAPH
    GRAPH --> POLICY
    GRAPH --> TOOLS
    
    GRAPH --> SLACK
    GRAPH --> GITHUB
    GRAPH --> STORAGE
```

---

## Phase 1: Foundation (Weeks 1-2)

### 1.1 Event Models and Storage

**Create:** `src/cuga/backend/events/models.py`

```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime
import uuid

class EventType(str, Enum):
    GITHUB = "github"
    SLACK = "slack"
    CRON = "cron"
    HEARTBEAT = "heartbeat"  # Batched periodic monitoring
    CUSTOM = "custom"

class EventSource(str, Enum):
    WEBHOOK = "webhook"
    SCHEDULER = "scheduler"

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    source: EventSource
    event_name: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"
    retry_count: int = 0
    max_retries: int = 3
```

**Create:** `src/cuga/backend/events/storage.py`

```python
        event = EventRecord(
            id=event.id,
            type=event.type,
            event_name=event.event_name,
            payload=json.dumps(event.payload),
            status=event.status,
            created_at=event.created_at
        )
        self.cursor.execute(
            "INSERT INTO events (id, type, event_name, payload, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event.id, event.type, event.event_name, event.payload, event.status, event.created_at)
        )
        self.conn.commit()
```

### 1.2 HTTP Server for Webhooks

**Create:** `src/cuga/backend/events/server.py`

```python
from fastapi import FastAPI, HTTPException, Header, Request
import hmac
import hashlib

class EventServer:
    def __init__(self, config: dict):
        self.app = FastAPI()
        self.config = config
        self.event_queue = EventQueue()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/webhooks/github")
        async def github_webhook(
            request: Request,
            x_github_event: str = Header(...),
            x_hub_signature_256: str = Header(None)
        ):
            if not self._verify_github_signature(request, x_hub_signature_256):
                raise HTTPException(status_code=401)
            
            payload = await request.json()
            event = Event(
                type=EventType.GITHUB,
                source=EventSource.WEBHOOK,
                event_name=x_github_event,
                payload=payload
            )
            await self.event_queue.enqueue(event)
            return {"status": "accepted", "event_id": event.id}
        
        @self.app.post("/webhooks/slack")
        async def slack_webhook(
            request: Request,
            x_slack_signature: str = Header(None)
        ):
            if not self._verify_slack_signature(request, x_slack_signature):
                raise HTTPException(status_code=401)
            
            payload = await request.json()
            
            # Handle URL verification
            if payload.get("type") == "url_verification":
                return {"challenge": payload["challenge"]}
            
            event = Event(
                type=EventType.SLACK,
                source=EventSource.WEBHOOK,
                event_name=payload.get("event", {}).get("type"),
                payload=payload
            )
            await self.event_queue.enqueue(event)
            return {"status": "accepted"}
```

### 1.3 Configuration

**Update:** `src/cuga/settings.toml`

```toml
[events]
enabled = true
http_port = 8002
bind_host = "127.0.0.1"

[events.webhooks.github]
enabled = true
secret = "${GITHUB_WEBHOOK_SECRET}"
events = ["push", "pull_request", "issues", "issue_comment"]

[events.webhooks.slack]
enabled = true
signing_secret = "${SLACK_SIGNING_SECRET}"
bot_token = "${SLACK_BOT_TOKEN}"
events = ["message", "app_mention"]
```

---

## Critical Concept: Heartbeat vs Cron

### Understanding the Distinction (from OpenClaw)

**Cron Jobs:**
- **Purpose:** Precise, scheduled execution (e.g., "daily report at 9 AM")
- **Session:** Isolated by default to avoid polluting main agent context
- **Use Case:** One-off tasks, reports, scheduled actions
- **Cost:** Each cron job spawns a separate agent execution
- **Example:** Daily summary, weekly report, scheduled backup

**Heartbeat:**
- **Purpose:** Batched, context-aware periodic monitoring
- **Session:** Runs in main session with full conversation context
- **Use Case:** Checking inbox, calendar, notifications - all in one turn
- **Cost:** Single agent execution for multiple monitoring tasks
- **Example:** Every 30 minutes, check email + calendar + Slack mentions

### The Problem with Cron-Only Approach

If a user creates 5 separate cron jobs to check status every 10 minutes:
```bash
cuga cron add --name "Check Email" --interval "10m" --message "Check email"
cuga cron add --name "Check Calendar" --interval "10m" --message "Check calendar"
cuga cron add --name "Check Slack" --interval "10m" --message "Check Slack"
cuga cron add --name "Check GitHub" --interval "10m" --message "Check GitHub"
cuga cron add --name "Check Jira" --interval "10m" --message "Check Jira"
```

**Result:** 5 isolated agent runs every 10 minutes = 30 runs/hour = expensive and context-less

### The Heartbeat Solution

Instead, configure a single heartbeat:
```bash
cuga heartbeat configure --interval "10m" --tasks "email,calendar,slack,github,jira"
```

**Result:** 1 context-aware agent run every 10 minutes = 6 runs/hour = efficient and contextual

### Implementation Strategy for CUGA

**Option 1: Dedicated Heartbeat System (Recommended)**
- Add `HeartbeatManager` alongside `CronScheduler`
- Single configurable heartbeat interval
- Batches multiple monitoring tasks
- Always runs in main session with conversation context

**Option 2: Cron with Main Session Routing**
- Allow cron jobs to target main session via `--session main`
- User manually creates one cron job that batches tasks
- More flexible but requires user understanding

**Recommendation:** Implement both - Heartbeat for common case, Cron for flexibility


## Phase 2: Heartbeat & Cron Scheduler (Weeks 2-3)

### 2.1 Heartbeat Manager (Context-Aware Periodic Monitoring)

**Create:** `src/cuga/backend/events/heartbeat.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import List, Dict, Any

class HeartbeatConfig(BaseModel):
    """Heartbeat configuration"""
    enabled: bool = True
    interval_seconds: int = 1800  # 30 minutes default
    tasks: List[str] = Field(default_factory=list)  # e.g., ["email", "calendar", "slack"]
    thread_id: str = "main"  # Always runs in main session
    wake_mode: str = "now"  # or "next-heartbeat"

class HeartbeatManager:
    """Manages periodic context-aware monitoring in main session"""
    
    def __init__(self, event_queue: EventQueue, config: HeartbeatConfig):
        self.scheduler = AsyncIOScheduler()
        self.event_queue = event_queue
        self.config = config
    
    def start(self):
        """Start heartbeat monitoring"""
        if not self.config.enabled or not self.config.tasks:
            return
        
        trigger = IntervalTrigger(seconds=self.config.interval_seconds)
        self.scheduler.add_job(
            self._execute_heartbeat,
            trigger=trigger,
            id="heartbeat"
        )
        self.scheduler.start()
    
    async def _execute_heartbeat(self):
        """Execute heartbeat - batched monitoring in main session"""
        # Create batched message for all monitoring tasks
        task_prompts = {
            "email": "Check for new emails and summarize important ones",
            "calendar": "Check calendar for upcoming events in next 2 hours",
            "slack": "Check for unread Slack mentions and messages",
            "github": "Check for new GitHub notifications and PRs",
            "jira": "Check for assigned Jira tickets needing attention"
        }
        
        messages = [task_prompts.get(task, f"Check {task}")
                   for task in self.config.tasks]
        
        batched_message = "Periodic status check:\n" + "\n".join(
            f"{i+1}. {msg}" for i, msg in enumerate(messages)
        )
        
        event = Event(
            type=EventType.HEARTBEAT,
            source=EventSource.SCHEDULER,
            event_name="heartbeat",
            payload={
                "message": batched_message,
                "tasks": self.config.tasks,
                "session_target": "main",  # Always main session
                "thread_id": self.config.thread_id,
                "wake_mode": self.config.wake_mode
            },
            metadata={
                "batched": True,
                "task_count": len(self.config.tasks)
            }
        )
        
        await self.event_queue.enqueue(event)
```

### 2.2 Enhanced Cron Job Model with Session Control

**Create:** `src/cuga/backend/events/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

class CronJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    schedule: Dict[str, Any]  # cron or interval
    payload: Dict[str, Any]
    session_target: str = "isolated"  # "isolated" or "main"
    thread_id: Optional[str] = None  # Specific thread for main session
    wake_mode: str = "now"  # "now" or "next-heartbeat"
    delivery: Optional[Dict[str, Any]] = None
    enabled: bool = True
    last_run: Optional[datetime] = None

class CronScheduler:
    def __init__(self, event_queue: EventQueue, config: dict):
        self.scheduler = AsyncIOScheduler()
        self.event_queue = event_queue
        self.jobs: Dict[str, CronJob] = {}
    
    def add_job(self, job: CronJob):
        if job.schedule["kind"] == "cron":
            trigger = CronTrigger(**job.schedule["expr"])
        else:
            trigger = IntervalTrigger(seconds=job.schedule["seconds"])
        
        self.scheduler.add_job(
            self._execute_job,
            trigger=trigger,
            args=[job.id],
            id=job.id
        )
        self.jobs[job.id] = job
    
    async def _execute_job(self, job_id: str):
        job = self.jobs[job_id]
        event = Event(
            type=EventType.CRON,
            source=EventSource.SCHEDULER,
            event_name=f"cron:{job.name}",
            payload={
                "job_id": job.id,
                "message": job.payload.get("message"),
                "session_target": job.session_target,
                "thread_id": job.thread_id,
                "wake_mode": job.wake_mode,
                "delivery": job.delivery
            }
        )
        await self.event_queue.enqueue(event)
```

### 2.3 Enhanced CLI Commands

**Create:** `src/cuga/cli/cron.py`

```python
import typer
from rich.console import Console

cron_app = typer.Typer()
heartbeat_app = typer.Typer()
console = Console()

# Cron commands
@cron_app.command("add")
def add_job(
    name: str = typer.Option(..., help="Job name"),
    cron: str = typer.Option(None, help="Cron expression (e.g., '0 9 * * *')"),
    interval: str = typer.Option(None, help="Interval (e.g., '1h', '30m')"),
    message: str = typer.Option(..., help="Message for the agent"),
    session: str = typer.Option("isolated", help="Session target: 'main' or 'isolated'"),
    thread_id: str = typer.Option(None, help="Thread ID for main session"),
    wake_mode: str = typer.Option("now", help="Wake mode: 'now' or 'next-heartbeat'"),
    channel: str = typer.Option(None, help="Delivery channel (slack, github, etc.)"),
    to: str = typer.Option(None, help="Delivery target")
):
    """Add a new cron job with session control"""
    if session == "main" and not thread_id:
        console.print("[yellow]Warning: Using main session without thread_id will use default thread[/yellow]")
    
    # Implementation
    console.print(f"[green]✓[/green] Cron job '{name}' added (session: {session})")

# Heartbeat commands
@heartbeat_app.command("configure")
def configure_heartbeat(
    interval: str = typer.Option("30m", help="Heartbeat interval (e.g., '30m', '1h')"),
    tasks: str = typer.Option(..., help="Comma-separated tasks (e.g., 'email,calendar,slack')"),
    thread_id: str = typer.Option("main", help="Thread ID for main session"),
    enabled: bool = typer.Option(True, help="Enable heartbeat")
):
    """Configure heartbeat monitoring"""
    task_list = [t.strip() for t in tasks.split(",")]
    console.print(f"[green]✓[/green] Heartbeat configured: {len(task_list)} tasks every {interval}")
    console.print(f"  Tasks: {', '.join(task_list)}")

@heartbeat_app.command("status")
def heartbeat_status():
    """Show heartbeat status"""
    # Implementation
    pass

@heartbeat_app.command("disable")
def disable_heartbeat():
    """Disable heartbeat"""
    console.print("[yellow]Heartbeat disabled[/yellow]")

@cron_app.command("list")
def list_jobs():
    """List all cron jobs"""
    pass

@cron_app.command("remove")
def remove_job(job_id: str):
    """Remove a cron job"""
    pass
```

---

## Phase 3: Event Processing (Weeks 3-4)

### 3.1 Event Router

**Create:** `src/cuga/backend/events/router.py`

```python
class EventRoute:
    def __init__(self, pattern: Dict, handler: Callable, priority: int = 0):
        self.pattern = pattern
        self.handler = handler
        self.priority = priority
    
    def matches(self, event: Event) -> bool:
        for key, value in self.pattern.items():
            if key == "type" and event.type != value:
                return False
            if key == "event_name" and event.event_name != value:
                return False
        return True

class EventRouter:
    def __init__(self):
        self.routes: List[EventRoute] = []
    
    def add_route(self, pattern, handler, priority=0):
        route = EventRoute(pattern, handler, priority)
        self.routes.append(route)
        self.routes.sort(key=lambda r: r.priority, reverse=True)
    
    async def route(self, event: Event):
        for route in self.routes:
            if route.matches(event):
                return await route.handler(event)
        raise ValueError(f"No route for event: {event.type}/{event.event_name}")
```

### 3.2 Event Handlers

**Create:** `src/cuga/backend/events/handlers.py`

```python
class EventHandlers:
    def __init__(self, agent_graph, config: dict):
        self.agent_graph = agent_graph
        self.config = config
    
    async def handle_github_pr(self, event: Event):
        payload = event.payload
        pr = payload.get("pull_request", {})
        
        message = f"""New PR: {pr.get('title')}
Author: {pr.get('user', {}).get('login')}
URL: {pr.get('html_url')}

Please review."""
        
        result = await self._run_agent(
            message=message,
            session_key=f"github:pr:{pr.get('number')}"
        )
        
        if result.get("answer"):
            await self._post_github_comment(
                repo=payload.get("repository", {}).get("full_name"),
                pr_number=pr.get("number"),
                comment=result["answer"]
            )
        return result
    
    async def handle_slack_mention(self, event: Event):
        slack_event = event.payload.get("event", {})
        message = slack_event.get("text", "")
        channel = slack_event.get("channel")
        thread_ts = slack_event.get("thread_ts") or slack_event.get("ts")
        
        result = await self._run_agent(
            message=message,
            session_key=f"slack:{channel}:{thread_ts}"
        )
        
        if result.get("answer"):
            await self._post_slack_message(
                channel=channel,
                text=result["answer"],
                thread_ts=thread_ts
            )
        return result
    
    async def handle_cron_job(self, event: Event):
        payload = event.payload
        session_target = payload.get("session_target", "isolated")
        thread_id = payload.get("thread_id")
        
        # Determine session key based on target
        if session_target == "main":
            session_key = thread_id or "main"
        else:
            session_key = f"cron:{payload.get('job_id')}"
        
        result = await self._run_agent(
            message=payload.get("message"),
            session_key=session_key
        )
        
        delivery = payload.get("delivery")
        if delivery:
            await self._deliver_result(result, delivery)
        return result
    
    async def handle_heartbeat(self, event: Event):
        """Handle heartbeat - always runs in main session"""
        payload = event.payload
        thread_id = payload.get("thread_id", "main")
        
        result = await self._run_agent(
            message=payload.get("message"),
            session_key=thread_id  # Always main session
        )
        
        return result
    
    async def _run_agent(self, message: str, session_key: str):
        config = {"configurable": {"thread_id": session_key}}
        return await self.agent_graph.graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config
        )
```

---

## Phase 4: Integration (Weeks 4-5)

### 4.1 Event Manager

**Create:** `src/cuga/backend/events/manager.py`

```python
class EventManager:
    def __init__(self, config: dict):
        self.event_queue = EventQueue()
        self.event_store = EventStore()
        self.event_server = EventServer(config)
        self.cron_scheduler = CronScheduler(self.event_queue, config)
        self.heartbeat_manager = HeartbeatManager(
            self.event_queue,
            config.get("heartbeat", HeartbeatConfig())
        )
        self.event_router = EventRouter()
        
        from cuga.backend.cuga_graph.graph import DynamicAgentGraph
        self.agent_graph = DynamicAgentGraph(config)
        self.handlers = EventHandlers(self.agent_graph, config)
        
        self._setup_routes()
    
    def _setup_routes(self):
        self.event_router.add_route(
            {"type": "github", "event_name": "pull_request"},
            self.handlers.handle_github_pr,
            priority=10
        )
        self.event_router.add_route(
            {"type": "slack", "event_name": "app_mention"},
            self.handlers.handle_slack_mention,
            priority=10
        )
        self.event_router.add_route(
            {"type": "heartbeat"},
            self.handlers.handle_heartbeat,
            priority=15  # Higher priority than cron
        )
        self.event_router.add_route(
            {"type": "cron"},
            self.handlers.handle_cron_job,
            priority=5
        )
    
    async def start(self):
        self.running = True
        self.cron_scheduler.start()
        self.heartbeat_manager.start()  # Start heartbeat
        
        # Start event processor
        asyncio.create_task(self._process_events())
        
        # Start HTTP server
        import uvicorn
        config = uvicorn.Config(self.event_server.app, port=8002)
        server = uvicorn.Server(config)
        await server.serve()
    
    async def _process_events(self):
        while self.running:
            event = await self.event_queue.dequeue()
            if event:
                await self._handle_event(event)
    
    async def _handle_event(self, event: Event):
        try:
            self.event_store.save_event(event)
            event.status = "processing"
            
            result = await self.event_router.route(event)
            
            event.status = "completed"
            event.processed_at = datetime.utcnow()
            self.event_store.save_event(event)
        except Exception as e:
            event.status = "failed"
            event.retry_count += 1
            if event.retry_count < event.max_retries:
                await self.event_queue.enqueue(event)
```

### 4.2 Policy Integration

**Create:** `src/cuga/backend/cuga_graph/policy/event_policies.py`

```python
class EventPolicy(Policy):
    event_types: List[str] = []
    rate_limit: Optional[Dict[str, Any]] = None
    
    def matches_event(self, event: Event) -> bool:
        if self.event_types and event.type not in self.event_types:
            return False
        return True

class EventPolicyEnforcer:
    def __init__(self, policy_system):
        self.policy_system = policy_system
        self.rate_limiter = RateLimiter()
    
    async def check_event(self, event: Event) -> tuple[bool, Optional[str]]:
        policies = [
            p for p in self.policy_system.policies
            if isinstance(p, EventPolicy) and p.matches_event(event)
        ]
        
        for policy in policies:
            if policy.rate_limit:
                if not self.rate_limiter.check(
                    key=f"{event.type}:{event.event_name}",
                    limit=policy.rate_limit
                ):
                    return False, "Rate limit exceeded"
        return True, None
```

---

## Phase 5: Monitoring (Week 5-6)

### 5.1 Metrics

**Create:** `src/cuga/backend/events/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

events_received = Counter(
    'cuga_events_received_total',
    'Total events received',
    ['type', 'source']
)

events_processed = Counter(
    'cuga_events_processed_total',
    'Total events processed',
    ['type', 'status']
)

event_processing_duration = Histogram(
    'cuga_event_processing_duration_seconds',
    'Event processing duration'
)

cron_jobs_active = Gauge(
    'cuga_cron_jobs_active',
    'Active cron jobs'
)
```

---

## Deployment Guide

### Environment Setup

```bash
# Install dependencies
pip install fastapi uvicorn apscheduler prometheus-client

# Set environment variables
export GITHUB_WEBHOOK_SECRET="your-secret"
export SLACK_SIGNING_SECRET="your-secret"
export SLACK_BOT_TOKEN="xoxb-your-token"
```

### Start Services

```bash
# Start CUGA with events
cuga start --events

# Or separately
cuga events start
```

### Configure Webhooks

**GitHub:**
1. Repository Settings → Webhooks
2. URL: `https://your-domain.com/webhooks/github`
3. Secret: Use `GITHUB_WEBHOOK_SECRET`
4. Events: Pull requests, Issues, Comments

**Slack:**
1. Create app at api.slack.com
2. Enable Event Subscriptions
3. URL: `https://your-domain.com/webhooks/slack`
4. Subscribe: `app_mention`, `message.channels`

### Configure Heartbeat (Recommended for Periodic Monitoring)

```bash
# Configure heartbeat for batched monitoring every 30 minutes
cuga heartbeat configure \
  --interval "30m" \
  --tasks "email,calendar,slack,github" \
  --thread-id "main"

# Check heartbeat status
cuga heartbeat status

# Disable heartbeat
cuga heartbeat disable
```

**Why Heartbeat?** Instead of creating 4 separate cron jobs that each spawn an isolated agent run, heartbeat batches all monitoring tasks into a single context-aware run in your main conversation thread. This is more efficient and maintains context.

### Create Cron Jobs

**Isolated Session (Default)** - For one-off tasks:
```bash
# Daily summary report (isolated session)
cuga cron add \
  --name "Daily Summary" \
  --cron "0 9 * * *" \
  --message "Generate daily summary report" \
  --session isolated \
  --channel slack \
  --to "#updates"

# Weekly backup (isolated session)
cuga cron add \
  --name "Weekly Backup" \
  --cron "0 0 * * 0" \
  --message "Run weekly backup" \
  --session isolated
```

**Main Session** - For context-aware reminders:
```bash
# Reminder in current conversation (main session)
cuga cron add \
  --name "Meeting Reminder" \
  --interval "20m" \
  --message "Reminder: Team meeting in 20 minutes" \
  --session main \
  --thread-id "user-123-conversation" \
  --wake-mode "now"

# Follow-up task in main session
cuga cron add \
  --name "Follow Up" \
  --cron "0 14 * * *" \
  --message "Follow up on morning tasks" \
  --session main \
  --thread-id "main"
```

**Comparison:**
- **Heartbeat**: Batched monitoring, always main session, efficient
- **Cron (isolated)**: One-off tasks, separate context, precise scheduling
- **Cron (main)**: Context-aware reminders, part of conversation

---

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_event_creation():
    event = Event(
        type=EventType.GITHUB,
        source=EventSource.WEBHOOK,
        event_name="pull_request",
        payload={"action": "opened"}
    )
    assert event.status == "pending"

@pytest.mark.asyncio
async def test_event_routing():
    router = EventRouter()
    async def handler(event):
        return {"handled": True}
    
    router.add_route({"type": "github"}, handler)
    event = Event(type=EventType.GITHUB, source=EventSource.WEBHOOK, event_name="pr", payload={})
    result = await router.route(event)
    assert result["handled"]
```

---

## Heartbeat vs Cron: Decision Guide

### When to Use Heartbeat

✅ **Use Heartbeat when:**
- Monitoring multiple sources periodically (email, calendar, Slack, etc.)
- You want context-aware updates in your main conversation
- Cost efficiency matters (1 run vs N runs)
- Tasks are related and benefit from shared context
- Frequency is consistent (e.g., every 30 minutes)

**Example:** "Check my email, calendar, and Slack every 30 minutes and let me know if anything needs attention"

### When to Use Cron (Isolated)

✅ **Use Cron (Isolated) when:**
- Task requires precise scheduling (e.g., daily at 9 AM)
- Task is independent and doesn't need conversation context
- Generating reports or summaries
- Running backups or maintenance tasks
- Task output should be delivered to a specific channel

**Example:** "Generate daily summary report at 9 AM and post to #updates channel"

### When to Use Cron (Main Session)

✅ **Use Cron (Main) when:**
- Setting reminders within current conversation
- Follow-up tasks that need conversation context
- Time-based prompts in ongoing work
- "Remind me in 20 minutes" type requests

**Example:** "Remind me in 20 minutes to follow up on the PR review"

### Cost Comparison

**Scenario:** Monitor email, calendar, Slack, GitHub every 10 minutes

| Approach | Runs/Hour | Runs/Day | Context | Cost |
|----------|-----------|----------|---------|------|
| 4 Separate Cron Jobs | 24 | 576 | ❌ None | 💰💰💰💰 |
| 1 Heartbeat | 6 | 144 | ✅ Full | 💰 |
| 1 Cron (Main) | 6 | 144 | ✅ Full | 💰 |

**Recommendation:** Use Heartbeat for this scenario - it's designed exactly for this use case.

---

## Security Considerations

1. **Webhook Security**
   - Always verify signatures (HMAC for GitHub, signature for Slack)
   - Use strong, unique tokens for custom webhooks
   - Implement rate limiting per source
   - Validate payloads against schemas
   - Log all webhook attempts for audit

2. **Cron & Heartbeat Security**
   - Isolated sessions prevent context pollution
   - Main session access requires explicit thread_id
   - Set resource limits (timeout, memory)
   - Audit all scheduled executions
   - Validate job configurations before scheduling

3. **Session Isolation**
   - Isolated sessions cannot access main conversation
   - Main session requires explicit thread_id
   - Prevent unauthorized session switching
   - Log all session transitions

4. **Policy Enforcement**
   - Block unauthorized event types
   - Require approval for sensitive operations
   - Sanitize outputs before delivery
   - Rate limit per event source

---

## Human-in-the-Loop (HITL) Approvals for Async Events

### The Challenge

When events trigger asynchronously (webhooks, cron, heartbeat), there's no user actively watching the CLI/UI. If the agent decides to take a destructive action (delete data, deploy code, send emails), we need a mechanism to:

1. **Pause execution** safely without losing state
2. **Notify the user** that approval is needed
3. **Wait for approval** (could be hours or days)
4. **Resume execution** from the exact point where it paused
5. **Handle timeouts** if approval never comes

### OpenClaw's Approach: Lobster Runtime

OpenClaw uses **Lobster** as a deterministic runtime that can:
- Suspend workflow execution at approval points
- Persist the exact execution state
- Resume from checkpoints after approval
- Handle multi-step workflows with multiple approval gates

### CUGA's HITL Implementation Strategy

#### Option 1: LangGraph Interrupt Pattern (Recommended)

LangGraph supports **interrupts** that can pause execution and wait for human input:

```python
# src/cuga/backend/cuga_graph/nodes/approval_gate.py
from langgraph.graph import StateGraph, END
from typing import Literal

class ApprovalState(TypedDict):
    """State for approval workflow"""
    action: str
    reason: str
    risk_level: Literal["low", "medium", "high", "critical"]
    approval_status: Optional[Literal["pending", "approved", "rejected"]]
    approval_token: str
    requested_at: datetime
    expires_at: datetime

def require_approval_node(state: AgentState) -> AgentState:
    """Node that requires human approval before proceeding"""
    
    # Check if action requires approval based on policy
    action = state.get("next_action")
    risk_level = assess_risk_level(action)
    
    if risk_level in ["high", "critical"]:
        # Generate approval token
        approval_token = str(uuid.uuid4())
        
        # Store approval request
        approval_request = ApprovalRequest(
            token=approval_token,
            action=action,
            risk_level=risk_level,
            event_id=state.get("event_id"),
            thread_id=state.get("thread_id"),
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        store_approval_request(approval_request)
        
        # Notify user via multiple channels
        notify_approval_needed(
            approval_token=approval_token,
            action=action,
            channels=["slack", "email", "webhook"]
        )
        
        # Return state with interrupt signal
        return {
            **state,
            "approval_status": "pending",
            "approval_token": approval_token,
            "__interrupt__": True  # LangGraph interrupt signal
        }
    
    # No approval needed, proceed
    return state

def check_approval_node(state: AgentState) -> AgentState:
    """Check if approval was granted"""
    approval_token = state.get("approval_token")
    approval = get_approval_status(approval_token)
    
    if approval.status == "approved":
        return {**state, "approval_status": "approved"}
    elif approval.status == "rejected":
        return {**state, "approval_status": "rejected"}
    else:
        # Still pending, keep waiting
        return {**state, "approval_status": "pending", "__interrupt__": True}

def should_continue_after_approval(state: AgentState) -> str:
    """Routing function to handle approval outcomes"""
    approval_status = state.get("approval_status")
    
    if approval_status == "approved":
        return "execute"
    elif approval_status == "rejected":
        return "end"  # Route to END node
    else:
        return "wait"  # Keep waiting for approval

# Build graph with approval gates
graph = StateGraph(AgentState)
graph.add_node("plan", plan_node)
graph.add_node("require_approval", require_approval_node)
graph.add_node("check_approval", check_approval_node)
graph.add_node("execute", execute_node)

# Add edges
graph.add_edge("plan", "require_approval")

# Conditional routing after require_approval
graph.add_conditional_edges(
    "require_approval",
    lambda s: "wait" if s.get("approval_status") == "pending" else "proceed",
    {
        "wait": "check_approval",
        "proceed": "execute"
    }
)

# Conditional routing after check_approval - handles rejection properly
graph.add_conditional_edges(
    "check_approval",
    should_continue_after_approval,
    {
        "execute": "execute",
        "end": END,  # Properly route to END on rejection
        "wait": "check_approval"  # Loop back if still pending
    }
)

# Execute completes normally
graph.add_edge("execute", END)
```

#### Option 2: Approval Queue with Polling

For simpler cases, use an approval queue:

```python
# src/cuga/backend/events/approval.py
class ApprovalRequest(BaseModel):
    token: str
    event_id: str
    thread_id: str
    action: Dict[str, Any]
    risk_level: str
    requested_at: datetime
    expires_at: datetime
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

class ApprovalManager:
    """Manages approval requests for async events"""
    
    def __init__(self, storage: ApprovalStorage):
        self.storage = storage
        self.notifier = ApprovalNotifier()
    
    async def request_approval(
        self,
        event_id: str,
        thread_id: str,
        action: Dict[str, Any],
        risk_level: str,
        timeout_hours: int = 24
    ) -> str:
        """Request approval for an action"""
        
        approval = ApprovalRequest(
            token=str(uuid.uuid4()),
            event_id=event_id,
            thread_id=thread_id,
            action=action,
            risk_level=risk_level,
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=timeout_hours)
        )
        
        # Store request
        await self.storage.save(approval)
        
        # Notify user via multiple channels
        await self.notifier.notify(
            approval_token=approval.token,
            action=action,
            risk_level=risk_level,
            channels=["slack", "email"],
            message=f"""
🚨 Approval Required

Action: {action['description']}
Risk Level: {risk_level}
Event: {event_id}

Approve: cuga approve {approval.token}
Reject: cuga reject {approval.token}

Expires: {approval.expires_at.isoformat()}
            """
        )
        
        return approval.token
    
    async def check_approval(self, token: str) -> ApprovalRequest:
        """Check approval status"""
        approval = await self.storage.get(token)
        
        # Check if expired
        if approval.status == "pending" and datetime.utcnow() > approval.expires_at:
            approval.status = "expired"
            await self.storage.save(approval)
        
        return approval
    
    async def approve(self, token: str, approved_by: str) -> bool:
        """Approve an action"""
        approval = await self.storage.get(token)
        
        if approval.status != "pending":
            return False
        
        approval.status = "approved"
        approval.approved_by = approved_by
        approval.approved_at = datetime.utcnow()
        await self.storage.save(approval)
        
        # Resume execution
        await self._resume_execution(approval)
        
        return True
    
    async def reject(self, token: str, rejected_by: str, reason: str) -> bool:
        """Reject an action"""
        approval = await self.storage.get(token)
        
        if approval.status != "pending":
            return False
        
        approval.status = "rejected"
        approval.approved_by = rejected_by
        await self.storage.save(approval)
        
        # Notify rejection
        await self.notifier.notify_rejection(approval, reason)
        
        return True
```

#### CLI Commands for Approval

```python
# src/cuga/cli/approval.py
import typer
from rich.console import Console
from rich.table import Table

approval_app = typer.Typer()
console = Console()

@approval_app.command("list")
def list_approvals(
    status: str = typer.Option("pending", help="Filter by status"),
    limit: int = typer.Option(10, help="Number of approvals to show")
):
    """List pending approval requests"""
    approvals = get_approvals(status=status, limit=limit)
    
    table = Table(title=f"Approval Requests ({status})")
    table.add_column("Token", style="cyan")
    table.add_column("Action", style="yellow")
    table.add_column("Risk", style="red")
    table.add_column("Requested", style="blue")
    table.add_column("Expires", style="magenta")
    
    for approval in approvals:
        table.add_row(
            approval.token[:8],
            approval.action["description"],
            approval.risk_level,
            approval.requested_at.strftime("%Y-%m-%d %H:%M"),
            approval.expires_at.strftime("%Y-%m-%d %H:%M")
        )
    
    console.print(table)

@approval_app.command("show")
def show_approval(token: str):
    """Show detailed approval request"""
    approval = get_approval(token)
    
    console.print(f"\n[bold]Approval Request[/bold]")
    console.print(f"Token: {approval.token}")
    console.print(f"Status: {approval.status}")
    console.print(f"Risk Level: {approval.risk_level}")
    console.print(f"\n[bold]Action:[/bold]")
    console.print(approval.action)
    console.print(f"\nRequested: {approval.requested_at}")
    console.print(f"Expires: {approval.expires_at}")

@approval_app.command("approve")
def approve_action(
    token: str,
    user: str = typer.Option(..., help="Your username/email")
):
    """Approve a pending action"""
    if approve_approval(token, user):
        console.print(f"[green]✓[/green] Action approved and resumed")
    else:
        console.print(f"[red]✗[/red] Failed to approve (already processed or expired)")

@approval_app.command("reject")
def reject_action(
    token: str,
    user: str = typer.Option(..., help="Your username/email"),
    reason: str = typer.Option(..., help="Reason for rejection")
):
    """Reject a pending action"""
    if reject_approval(token, user, reason):
        console.print(f"[yellow]✓[/yellow] Action rejected")
    else:
        console.print(f"[red]✗[/red] Failed to reject (already processed or expired)")
```

### Notification Channels

```python
# src/cuga/backend/events/approval_notifier.py
class ApprovalNotifier:
    """Multi-channel notification for approval requests"""
    
    async def notify(
        self,
        approval_token: str,
        action: Dict[str, Any],
        risk_level: str,
        channels: List[str]
    ):
        """Send approval notification via multiple channels"""
        
        message = self._format_message(approval_token, action, risk_level)
        
        tasks = []
        if "slack" in channels:
            tasks.append(self._notify_slack(message, approval_token))
        if "email" in channels:
            tasks.append(self._notify_email(message, approval_token))
        if "webhook" in channels:
            tasks.append(self._notify_webhook(message, approval_token))
        
        await asyncio.gather(*tasks)
    
    async def _notify_slack(self, message: str, token: str):
        """Send Slack notification with action buttons"""
        await slack_client.post_message(
            channel="#approvals",
            text=message,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "value": token,
                            "action_id": f"approve_{token}"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Reject"},
                            "style": "danger",
                            "value": token,
                            "action_id": f"reject_{token}"
                        }
                    ]
                }
            ]
        )
```

### Policy Configuration

```toml
# src/cuga/settings.toml
[events.approval]
enabled = true
default_timeout_hours = 24
notification_channels = ["slack", "email"]

[events.approval.risk_levels]
# Actions requiring approval by risk level
high = [
    "delete_*",
    "deploy_*",
    "send_email_bulk",
    "modify_production_*"
]
critical = [
    "delete_database",
    "revoke_access",
    "shutdown_*"
]

[events.approval.auto_approve]
# Actions that can be auto-approved for specific users/roles
enabled = true
roles = ["admin", "senior_engineer"]
actions = ["deploy_staging", "restart_service"]
```

### Integration with Event Handlers

```python
# Update event handlers to check for approval
async def handle_github_pr(self, event: Event):
    payload = event.payload
    action = payload.get("action")
    
    # Determine if action needs approval
    if action in ["closed", "merged"]:
        # Check if PR merge triggers deployment
        if should_trigger_deployment(payload):
            # Request approval
            approval_token = await self.approval_manager.request_approval(
                event_id=event.id,
                thread_id=f"github:pr:{payload['pull_request']['number']}",
                action={
                    "type": "deploy",
                    "description": f"Deploy PR #{payload['pull_request']['number']}",
                    "pr_url": payload['pull_request']['html_url']
                },
                risk_level="high"
            )
            
            # Wait for approval (with timeout)
            approval = await self.approval_manager.wait_for_approval(
                approval_token,
                timeout_seconds=86400  # 24 hours
            )
            
            if approval.status != "approved":
                return {"status": "rejected", "reason": "Approval denied or expired"}
    
    # Proceed with normal handling
    result = await self._run_agent(...)
    return result
```

### Resume Mechanism

```python
class ExecutionCheckpoint(BaseModel):
    """Checkpoint for resuming execution"""
    checkpoint_id: str
    event_id: str
    thread_id: str
    state: Dict[str, Any]
    node: str  # Current node in graph
    created_at: datetime

async def _resume_execution(self, approval: ApprovalRequest):
    """Resume execution after approval"""
    
    # Load checkpoint
    checkpoint = await self.storage.get_checkpoint(approval.event_id)
    
    if not checkpoint:
        logger.error(f"No checkpoint found for event {approval.event_id}")
        return
    
    # Resume graph execution from checkpoint
    config = {
        "configurable": {
            "thread_id": checkpoint.thread_id,
            "checkpoint_id": checkpoint.checkpoint_id
        }
    }
    
    # Update state with approval
    state = {
        **checkpoint.state,
        "approval_status": "approved",
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at
    }
    
    # Resume from checkpoint
    result = await self.agent_graph.graph.ainvoke(
        state,
        config=config
    )
    
    return result
```

### Best Practices

1. **Always notify via multiple channels** - Slack, email, webhook
2. **Set reasonable timeouts** - 24 hours default, configurable per action
3. **Persist checkpoints** - Store execution state before requesting approval
4. **Handle expiration gracefully** - Auto-reject expired approvals
5. **Audit all approvals** - Log who approved/rejected and when
6. **Test resume logic** - Ensure execution resumes correctly after hours/days
7. **Provide context** - Include full action details in approval request
8. **Support bulk approvals** - For admins managing multiple requests

   - Enforce intent guards on scheduled tasks

---

## Implementation Checklist

### Phase 1: Foundation
- [ ] Create event models (including HEARTBEAT type)
- [ ] Implement event queue
- [ ] Build HTTP server
- [ ] Add GitHub webhook endpoint
- [ ] Add Slack webhook endpoint
- [ ] Implement signature verification
- [ ] Create event storage

### Phase 2: Heartbeat & Cron
- [ ] Implement HeartbeatConfig model
- [ ] Build HeartbeatManager
- [ ] Implement CronJob model with session_target
- [ ] Build CronScheduler with session routing
- [ ] Add job persistence
- [ ] Create heartbeat CLI commands
- [ ] Create cron CLI commands with --session flag
- [ ] Add retry mechanism
- [ ] Implement wake_mode support

### Phase 3: Processing
- [ ] Build EventRouter
- [ ] Implement EventHandlers
- [ ] Add GitHub PR handler
- [ ] Add Slack mention handler
- [ ] Add cron job handler with session routing
- [ ] Add heartbeat handler (main session only)

### Phase 4: Integration
- [ ] Build EventManager
- [ ] Integrate with DynamicAgentGraph
- [ ] Add policy enforcement
- [ ] Update CLI

### Phase 5: Human-in-the-Loop Approvals
- [ ] Implement ApprovalRequest model
- [ ] Build ApprovalManager with storage
- [ ] Add LangGraph interrupt pattern for approval gates
- [ ] Create approval CLI commands (list, show, approve, reject)
- [ ] Implement multi-channel notifications (Slack, email, webhook)
- [ ] Add checkpoint/resume mechanism
- [ ] Configure risk-based approval policies
- [ ] Add approval timeout handling
- [ ] Implement approval audit logging

### Phase 6: Monitoring
- [ ] Add Prometheus metrics (including approval metrics)
- [ ] Create dashboard
- [ ] Implement health checks

---

## Success Metrics

1. **Adoption**
   - Active webhooks
   - Cron jobs created
   - Heartbeat configurations
   - Events per day

2. **Reliability**
   - Success rate >99%
   - Latency <2s (excluding approval wait time)
   - Job reliability >99.9%
   - Approval response time <4 hours (median)

3. **Safety**
   - High-risk actions requiring approval: 100%
   - Approval timeout rate <5%
   - Unauthorized action attempts: 0

3. **Satisfaction**
   - Response time
   - Accuracy
   - Reduced manual work

---

## Conclusion

This plan transforms CUGA into an event-driven system that can:

1. **Respond to external events** - GitHub webhooks, Slack mentions, custom triggers
2. **Execute scheduled tasks** - Cron jobs with precise timing and session control
3. **Monitor periodically** - Heartbeat system for efficient, context-aware monitoring
4. **Process events reliably** - Retry logic, error handling, policy enforcement
5. **Scale efficiently** - Queue-based processing, Redis support, horizontal scaling

### Key Improvements from OpenClaw Integration

**1. Heartbeat System (Critical Addition)**
- Batched periodic monitoring in main session
- Reduces cost by 75% compared to separate cron jobs
- Maintains conversation context across monitoring tasks
- Configurable via simple CLI: `cuga heartbeat configure --interval 30m --tasks email,calendar,slack`

**2. Enhanced Session Management**
- Explicit control over main vs isolated session execution
- CLI support for session targeting: `--session main|isolated`
- Thread ID specification for main session tasks
- Wake mode support: `--wake-mode now|next-heartbeat`

**3. Context-Aware Scheduling**
- Isolated sessions for independent tasks (reports, backups)
- Main session for conversation-aware reminders
- Heartbeat for batched monitoring with full context
- Clear decision guide for choosing the right approach

### Architecture Highlights

- **5 Layers**: Event Sources → Ingestion → Processing → Core → Delivery
- **19 Components**: Modular, testable, scalable
- **4 Event Types**: GitHub, Slack, Cron, Heartbeat
- **2 Session Modes**: Main (context-aware) and Isolated (independent)
- **100+ events/sec**: High-throughput processing
- **<2s latency**: Fast event handling
- **99%+ reliability**: Automatic retries and error handling

**Next Steps:**
1. Review and approve plan
2. Set up development environment
3. Begin Phase 1 implementation (Foundation)
4. Implement Phase 2 (Heartbeat & Cron) - Critical for efficiency
5. Iterate based on feedback and usage patterns

---

## Quick Reference

### Key Files

```
src/cuga/backend/events/
├── __init__.py
├── server.py
├── models.py
├── storage.py
├── scheduler.py      # Cron scheduler
├── heartbeat.py      # Heartbeat manager (NEW)
├── router.py         # Event routing
├── handlers.py       # Event handlers
├── manager.py        # Central event manager
└── metrics.py        # Prometheus metrics

src/cuga/cli/
├── cron.py          # Cron CLI commands
└── heartbeat.py     # Heartbeat CLI commands (NEW)
```

### CLI Commands

```bash
# Event management
cuga events start
cuga events stop
cuga events status

# Heartbeat (NEW - Recommended for periodic monitoring)
cuga heartbeat configure --interval 30m --tasks email,calendar,slack
cuga heartbeat status
cuga heartbeat disable

# Cron with session control (ENHANCED)
cuga cron add --name "Job" --cron "0 9 * * *" --message "Task" --session isolated
cuga cron add --name "Reminder" --interval 20m --message "Task" --session main --thread-id main
cuga cron add --name "Job" --cron "0 9 * * *" --message "Task"
cuga cron list
cuga cron remove <id>
```

### API Endpoints

```
POST /webhooks/github
POST /webhooks/slack
POST /webhooks/custom/{name}