# Webhook Implementation - Clean Architecture Summary

## Overview

Successfully reorganized the webhook implementation with a clean separation between generic event infrastructure and integration-specific code.

## Architecture

```
src/cuga/backend/
├── events/                              # Generic Event Infrastructure
│   ├── models.py                        # ✅ Generic Event, EventType, etc.
│   ├── queue.py                         # ✅ Generic async event queue
│   ├── processor.py                     # ✅ Generic processor (routes to integrations)
│   ├── session_management.py            # ✅ Generic session routing
│   ├── approval_system.py               # ✅ Generic approval system
│   └── heartbeat.py                     # ✅ Generic heartbeat system
│
├── integrations/slack/                  # Slack-Specific Integration
│   ├── models.py                        # ✅ Slack data models
│   ├── client.py                        # ✅ Slack API client
│   ├── handler.py                       # ✅ Slack → CUGA event converter
│   ├── notification_channel.py          # ✅ CUGA → Slack sender
│   ├── processor.py                     # ✅ Slack event processor
│   ├── routes.py                        # ✅ Slack webhook endpoints
│   └── __init__.py                      # ✅ Exports all components
│
└── server/
    └── main.py                          # FastAPI app (needs integration)
```

## Component Responsibilities

### Generic Event Infrastructure (`events/`)

#### 1. Event Queue (`queue.py`)
- **Purpose**: Generic async queue for any event type
- **Features**:
  - In-memory queue with configurable max size
  - Background processor with error handling
  - Statistics tracking (processed, errors, queue size)
  - Graceful shutdown
- **Usage**: Works for Slack, GitHub, email, cron, etc.

#### 2. Event Processor (`processor.py`)
- **Purpose**: Routes events to integration-specific processors
- **Features**:
  - Session routing (main/isolated)
  - Processor registration by event type
  - Error handling and logging
- **Pattern**:
  ```python
  processor = EventProcessor(session_router)
  processor.register_processor(EventType.SLACK, slack_processor.process_event)
  processor.register_processor(EventType.GITHUB, github_processor.process_event)
  ```

#### 3. Session Management (`session_management.py`)
- **Purpose**: Routes events to appropriate sessions
- **Features**:
  - Main session (context-aware, shared state)
  - Isolated session (independent, no shared state)
  - Thread-based isolation

#### 4. Approval System (`approval_system.py`)
- **Purpose**: Human-in-the-loop approvals
- **Features**:
  - Async approval waiting
  - Policy-based matching
  - Multi-channel notifications

### Slack Integration (`integrations/slack/`)

#### 1. Slack Models (`models.py`)
- Pydantic models for Slack data structures
- SlackEvent, SlackUser, SlackChannel, etc.

#### 2. Slack Client (`client.py`)
- Async wrapper around slack-sdk
- Signature verification (HMAC-SHA256)
- Send messages, reactions, files, modals

#### 3. Slack Event Handler (`handler.py`)
- Converts Slack events → CUGA events
- Enriches with user/channel info
- Adds response routing information

#### 4. Slack Notification Channel (`notification_channel.py`)
- Sends CUGA responses → Slack
- Formats messages with blocks
- Handles approval buttons
- Status indicators (thinking, completion, error)

#### 5. Slack Event Processor (`processor.py`)
- **NEW**: Slack-specific event processing
- Handles messages, interactions, reactions
- Integrates with approval system
- Sends responses via notification channel

#### 6. Slack Webhook Routes (`routes.py`)
- **NEW**: FastAPI routes for Slack webhooks
- POST /webhooks/slack/events
- POST /webhooks/slack/commands
- POST /webhooks/slack/interactions
- GET /webhooks/slack/health
- Signature verification on all endpoints

## Data Flow

### 1. Slack Event → CUGA

```
User in Slack: "@CUGA help me"
    ↓
Slack API sends POST to /webhooks/slack/events
    ↓
Slack Routes (routes.py):
  - Verify signature
  - Parse payload
    ↓
Slack Event Handler (handler.py):
  - Convert to CUGA Event
  - Add response routing info
    ↓
Event Queue (queue.py):
  - Enqueue event
    ↓
Generic Event Processor (events/processor.py):
  - Route to session
  - Delegate to Slack processor
    ↓
Slack Event Processor (integrations/slack/processor.py):
  - Process message
  - Call CUGA agent (TODO)
  - Generate response
    ↓
Slack Notification Channel (notification_channel.py):
  - Format response
  - Send to Slack API
    ↓
User sees response in Slack
```

### 2. Approval Flow

```
CUGA needs approval for action
    ↓
Approval System creates request
    ↓
Slack Notification Channel:
  - Send message with [Approve] [Reject] buttons
    ↓
User clicks [Approve]
    ↓
Slack sends POST to /webhooks/slack/interactions
    ↓
Slack Routes:
  - Verify signature
  - Create interaction event
    ↓
Event Queue → Generic Processor → Slack Processor:
  - Handle approval action
  - Update approval system (TODO)
  - Send confirmation
    ↓
User sees "✅ Action approved"
```

## Integration with FastAPI

### Required Changes to `main.py`

```python
# 1. Import components
from cuga.backend.events.queue import EventQueue
from cuga.backend.events.processor import EventProcessor
from cuga.backend.events.session_management import SessionRouter
from cuga.backend.events.models import EventType
from cuga.backend.integrations.slack import (
    router as slack_router,
    initialize_slack,
    get_slack_processor
)

# 2. Add to AppState
class AppState:
    def __init__(self):
        # ... existing fields ...
        self.event_queue: Optional[EventQueue] = None
        self.event_processor: Optional[EventProcessor] = None
        self.session_router: Optional[SessionRouter] = None

# 3. Initialize in lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup ...
    
    # Initialize event system
    app_state.event_queue = EventQueue()
    app_state.session_router = SessionRouter()
    app_state.event_processor = EventProcessor(app_state.session_router)
    
    # Start event processor
    app_state.event_queue.start_processor(
        app_state.event_processor.process_event
    )
    
    # Initialize Slack integration
    if initialize_slack(app_state.event_queue):
        slack_processor = get_slack_processor()
        if slack_processor:
            app_state.event_processor.register_processor(
                EventType.SLACK,
                slack_processor.process_event
            )
    
    yield
    
    # Shutdown
    if app_state.event_queue:
        await app_state.event_queue.stop()

# 4. Include Slack routes
app = FastAPI(lifespan=lifespan)
# ... existing middleware ...
app.include_router(slack_router)
```

## Benefits of This Architecture

### 1. Clean Separation of Concerns
- Generic event infrastructure is reusable
- Integration-specific code is isolated
- Easy to understand and maintain

### 2. Extensibility
Adding a new integration (e.g., GitHub) follows the same pattern:
```
integrations/github/
├── models.py          # GitHub data models
├── client.py          # GitHub API client
├── handler.py         # GitHub → CUGA converter
├── processor.py       # GitHub event processor
└── routes.py          # GitHub webhook endpoints
```

### 3. Testability
- Each component can be tested independently
- Mock integration-specific processors for testing generic code
- Mock generic infrastructure for testing integration code

### 4. Maintainability
- Changes to Slack don't affect GitHub
- Changes to event queue don't affect integrations
- Clear boundaries and responsibilities

## Files Created

### Generic Infrastructure (3 files)
1. `src/cuga/backend/events/queue.py` (153 lines)
2. `src/cuga/backend/events/processor.py` (79 lines)
3. Existing: models.py, session_management.py, approval_system.py, heartbeat.py

### Slack Integration (2 new files)
1. `src/cuga/backend/integrations/slack/processor.py` (180 lines)
2. `src/cuga/backend/integrations/slack/routes.py` (283 lines)
3. Updated: `__init__.py` to export new components
4. Existing: models.py, client.py, handler.py, notification_channel.py

### Documentation (1 file)
1. `webhook-architecture-summary.md` (this file)

## Next Steps

### 1. Integrate with FastAPI (30 minutes)
- Modify `src/cuga/backend/server/main.py`
- Add imports, update AppState, update lifespan
- Include Slack router

### 2. Test with ngrok (1 hour)
- Start CUGA server
- Start ngrok tunnel
- Update Slack app URLs
- Test all event types:
  - URL verification ✓
  - App mention
  - Direct message
  - Slash command
  - Interaction (button click)

### 3. Integrate with CUGA Agent (2-3 hours)
- Connect Slack processor to actual CUGA agent
- Pass session context
- Handle agent responses
- Implement approval integration

### 4. Add Tests (2-3 hours)
- Unit tests for queue, processor, routes
- Integration tests for end-to-end flow
- Mock Slack API for testing

## Status

✅ **Architecture Complete**
- Clean separation of concerns
- Generic infrastructure reusable
- Slack integration isolated
- Ready for FastAPI integration

❌ **Pending**
- FastAPI integration (main.py changes)
- Testing with ngrok
- CUGA agent integration
- Unit/integration tests

## Estimated Time to Complete

- FastAPI integration: 30 min
- Testing: 1 hour
- Agent integration: 2-3 hours
- Tests: 2-3 hours

**Total**: 5.5-7.5 hours