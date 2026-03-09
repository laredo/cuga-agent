# Webhook Endpoints Implementation Plan

## Overview

Implement FastAPI webhook endpoints to receive events from Slack and integrate them with CUGA's existing event-driven system.

## Current State Analysis

### ✅ What We Have

1. **Slack Integration Code** (Complete)
   - `SlackClient` - Sends messages to Slack
   - `SlackEventHandler` - Converts Slack events to CUGA events
   - `SlackNotificationChannel` - Sends responses back to Slack
   - All models and utilities

2. **Event System** (Complete)
   - Event models (EventType.SLACK supported)
   - Session routing (main/isolated)
   - Approval system with notification channels
   - Heartbeat system

3. **CUGA FastAPI Server** (`src/cuga/backend/server/main.py`)
   - Existing FastAPI app with lifespan management
   - CORS middleware
   - Authentication system
   - Multiple route modules (manage_routes, secrets_routes)
   - AppState for global state management

### ❌ What's Missing

1. **Webhook Routes Module** - FastAPI routes for Slack webhooks
2. **Event Queue** - Queue for async event processing
3. **Event Processor** - Worker that processes events through CUGA agent
4. **Integration with AppState** - Add Slack components to app state

## Implementation Plan

### Phase 1: Create Event Queue (Simple In-Memory)

**File**: `src/cuga/backend/events/queue.py`

**Purpose**: Simple async queue for event processing

**Implementation**:
```python
import asyncio
from typing import Optional
from loguru import logger
from cuga.backend.events.models import Event

class EventQueue:
    """Simple in-memory event queue for async processing"""
    
    def __init__(self):
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def enqueue(self, event: Event):
        """Add event to queue"""
        await self.queue.put(event)
        logger.info(f"Enqueued event: {event.event_name} (id={event.id})")
    
    async def dequeue(self) -> Event:
        """Get next event from queue"""
        return await self.queue.get()
    
    def start_processor(self, processor_func):
        """Start background processor"""
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(
            self._process_loop(processor_func)
        )
        logger.info("Event processor started")
    
    async def _process_loop(self, processor_func):
        """Background loop that processes events"""
        while self._running:
            try:
                event = await self.dequeue()
                await processor_func(event)
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def stop(self):
        """Stop the processor"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Event processor stopped")
```

**Why In-Memory First**:
- Simple to implement
- No external dependencies
- Good for initial testing
- Can be replaced with Redis later

### Phase 2: Create Webhook Routes Module

**File**: `src/cuga/backend/server/slack_routes.py`

**Purpose**: FastAPI routes for Slack webhooks

**Implementation**:
```python
"""Slack webhook routes for CUGA"""

import json
import os
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, HTTPException, Header
from loguru import logger

from cuga.backend.integrations.slack import (
    SlackClient,
    SlackEventHandler,
    SlackNotificationChannel
)
from cuga.backend.events.queue import EventQueue

router = APIRouter(prefix="/webhooks/slack", tags=["slack"])

# Global instances (will be initialized in lifespan)
slack_client: Optional[SlackClient] = None
slack_handler: Optional[SlackEventHandler] = None
slack_notification: Optional[SlackNotificationChannel] = None
event_queue: Optional[EventQueue] = None


def initialize_slack_components(queue: EventQueue):
    """Initialize Slack components with credentials from environment"""
    global slack_client, slack_handler, slack_notification, event_queue
    
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    
    if not bot_token or not signing_secret:
        logger.warning(
            "Slack credentials not found. Set SLACK_BOT_TOKEN and "
            "SLACK_SIGNING_SECRET environment variables to enable Slack integration."
        )
        return False
    
    try:
        slack_client = SlackClient(
            bot_token=bot_token,
            signing_secret=signing_secret
        )
        slack_handler = SlackEventHandler(slack_client)
        slack_notification = SlackNotificationChannel(slack_client)
        event_queue = queue
        
        logger.info("✅ Slack integration initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Slack integration: {e}")
        return False


@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack Events API callbacks
    
    This endpoint receives events from Slack such as:
    - app_mention: When @CUGA is mentioned
    - message: Direct messages to CUGA
    - reaction_added/removed: Emoji reactions
    """
    if not slack_client or not slack_handler or not event_queue:
        raise HTTPException(
            status_code=503,
            detail="Slack integration not initialized"
        )
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify Slack signature for security
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = json.loads(body_str)
    
    # Handle URL verification challenge (first-time setup)
    if payload.get("type") == "url_verification":
        logger.info("Slack URL verification challenge received")
        return {"challenge": payload["challenge"]}
    
    # Handle event callback
    if payload.get("type") == "event_callback":
        try:
            event = await slack_handler.handle_event(payload)
            if event:
                await event_queue.enqueue(event)
                logger.info(
                    f"Slack event received: {event.event_name} "
                    f"from user {event.payload.get('user', {}).get('id')}"
                )
        except Exception as e:
            logger.error(f"Error handling Slack event: {e}")
            # Return 200 to prevent Slack retries for application errors
    
    return {"ok": True}


@router.post("/commands")
async def slack_commands(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack slash commands
    
    Supported commands:
    - /cuga [request]: Send request to CUGA
    - /cuga-approve [id]: Approve a pending action
    - /cuga-reject [id] [reason]: Reject a pending action
    - /cuga-status: Check CUGA status
    """
    if not slack_client or not slack_handler or not event_queue:
        raise HTTPException(
            status_code=503,
            detail="Slack integration not initialized"
        )
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    payload = {k: v[0] for k, v in parse_qs(body_str).items()}
    
    try:
        event = await slack_handler.handle_slash_command(payload)
        await event_queue.enqueue(event)
        
        logger.info(
            f"Slash command received: {payload['command']} "
            f"from user {payload['user_name']}"
        )
        
        # Immediate acknowledgment
        return {
            "response_type": "ephemeral",
            "text": "Processing your request..."
        }
    except Exception as e:
        logger.error(f"Error handling slash command: {e}")
        return {
            "response_type": "ephemeral",
            "text": f"Error: {str(e)}"
        }


@router.post("/interactions")
async def slack_interactions(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack interactive components
    
    This endpoint receives interactions such as:
    - Button clicks (e.g., approval buttons)
    - Select menu choices
    - Modal submissions
    """
    if not slack_client or not slack_handler or not event_queue:
        raise HTTPException(
            status_code=503,
            detail="Slack integration not initialized"
        )
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    form_data = parse_qs(body_str)
    payload = json.loads(form_data["payload"][0])
    
    try:
        event = await slack_handler.handle_interaction(payload)
        await event_queue.enqueue(event)
        
        logger.info(
            f"Interaction received: {payload['type']} "
            f"from user {payload['user']['id']}"
        )
        
        # Immediate acknowledgment
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling interaction: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/health")
async def slack_health():
    """Health check endpoint for Slack integration"""
    return {
        "status": "ok" if slack_client else "not_initialized",
        "integration": "slack",
        "components": {
            "client": slack_client is not None,
            "handler": slack_handler is not None,
            "notification": slack_notification is not None,
            "queue": event_queue is not None
        }
    }
```

### Phase 3: Create Event Processor

**File**: `src/cuga/backend/events/processor.py`

**Purpose**: Process events through CUGA agent

**Implementation**:
```python
"""Event processor for CUGA events"""

from typing import Optional
from loguru import logger

from cuga.backend.events.models import Event, EventType
from cuga.backend.events.session_management import SessionRouter
from cuga.backend.integrations.slack import SlackNotificationChannel


class EventProcessor:
    """Processes events through CUGA agent"""
    
    def __init__(
        self,
        session_router: SessionRouter,
        slack_notification: Optional[SlackNotificationChannel] = None
    ):
        self.session_router = session_router
        self.slack_notification = slack_notification
    
    async def process_event(self, event: Event):
        """Process a single event"""
        logger.info(f"Processing event: {event.event_name} (type={event.type})")
        
        try:
            # Route to appropriate session
            session_context = self.session_router.route_event(event)
            logger.info(
                f"Event routed to {session_context.session_type} session "
                f"(thread_id={session_context.thread_id})"
            )
            
            # Handle different event types
            if event.type == EventType.SLACK:
                await self._process_slack_event(event, session_context)
            elif event.type == EventType.GITHUB:
                await self._process_github_event(event, session_context)
            elif event.type == EventType.CRON:
                await self._process_cron_event(event, session_context)
            elif event.type == EventType.HEARTBEAT:
                await self._process_heartbeat_event(event, session_context)
            else:
                logger.warning(f"Unknown event type: {event.type}")
        
        except Exception as e:
            logger.error(f"Error processing event {event.id}: {e}")
            
            # Send error notification if Slack event
            if event.type == EventType.SLACK and self.slack_notification:
                await self._send_slack_error(event, str(e))
    
    async def _process_slack_event(self, event: Event, session_context):
        """Process Slack event"""
        # TODO: Integrate with CUGA agent
        # For now, just send a test response
        
        if self.slack_notification:
            response_channel = event.payload.get("response_channel")
            response_thread_ts = event.payload.get("response_thread_ts")
            
            if response_channel:
                # Send thinking indicator
                if response_thread_ts:
                    await self.slack_notification.send_thinking_indicator(
                        channel=response_channel,
                        message_ts=response_thread_ts
                    )
                
                # TODO: Call CUGA agent here
                # response = await cuga_agent.process(event)
                
                # For now, send a placeholder response
                await self.slack_notification.send_response(
                    text=f"Received your message: {event.payload.get('text', 'N/A')}",
                    channel=response_channel,
                    thread_ts=response_thread_ts
                )
                
                logger.info(f"Sent response to Slack channel {response_channel}")
    
    async def _process_github_event(self, event: Event, session_context):
        """Process GitHub event"""
        # TODO: Implement GitHub event processing
        logger.info(f"GitHub event processing not yet implemented: {event.event_name}")
    
    async def _process_cron_event(self, event: Event, session_context):
        """Process cron event"""
        # TODO: Implement cron event processing
        logger.info(f"Cron event processing not yet implemented: {event.event_name}")
    
    async def _process_heartbeat_event(self, event: Event, session_context):
        """Process heartbeat event"""
        # TODO: Implement heartbeat event processing
        logger.info(f"Heartbeat event processing not yet implemented: {event.event_name}")
    
    async def _send_slack_error(self, event: Event, error_message: str):
        """Send error message to Slack"""
        response_channel = event.payload.get("response_channel")
        response_thread_ts = event.payload.get("response_thread_ts")
        
        if response_channel and self.slack_notification:
            await self.slack_notification.send_response(
                text=f"❌ Error processing your request: {error_message}",
                channel=response_channel,
                thread_ts=response_thread_ts
            )
```

### Phase 4: Integrate with FastAPI App

**File**: `src/cuga/backend/server/main.py` (modifications)

**Changes needed**:

1. **Import new modules**:
```python
from cuga.backend.events.queue import EventQueue
from cuga.backend.events.processor import EventProcessor
from cuga.backend.events.session_management import SessionRouter
from cuga.backend.server import slack_routes
```

2. **Add to AppState**:
```python
class AppState:
    def __init__(self):
        # ... existing fields ...
        self.event_queue: Optional[EventQueue] = None
        self.event_processor: Optional[EventProcessor] = None
        self.session_router: Optional[SessionRouter] = None
```

3. **Initialize in lifespan**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application is starting up...")
    
    # ... existing startup code ...
    
    # Initialize event system
    try:
        from cuga.backend.events.queue import EventQueue
        from cuga.backend.events.processor import EventProcessor
        from cuga.backend.events.session_management import SessionRouter
        
        app_state.event_queue = EventQueue()
        app_state.session_router = SessionRouter()
        app_state.event_processor = EventProcessor(
            session_router=app_state.session_router,
            slack_notification=None  # Will be set by slack_routes
        )
        
        # Start event processor
        app_state.event_queue.start_processor(
            app_state.event_processor.process_event
        )
        
        logger.info("✅ Event system initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize event system: {e}")
    
    # Initialize Slack integration
    if app_state.event_queue:
        try:
            from cuga.backend.server.slack_routes import initialize_slack_components
            
            if initialize_slack_components(app_state.event_queue):
                # Update processor with Slack notification channel
                from cuga.backend.server.slack_routes import slack_notification
                if slack_notification:
                    app_state.event_processor.slack_notification = slack_notification
        except Exception as e:
            logger.warning(f"Failed to initialize Slack integration: {e}")
    
    yield
    
    # Shutdown
    logger.info("Application is shutting down...")
    
    # Stop event processor
    if app_state.event_queue:
        await app_state.event_queue.stop()
    
    # ... existing shutdown code ...
```

4. **Include Slack routes**:
```python
# After creating the FastAPI app
app = FastAPI(lifespan=lifespan)

# ... existing middleware and routes ...

# Include Slack webhook routes
app.include_router(slack_routes.router)
```

## Implementation Steps

### Step 1: Create Event Queue
1. Create `src/cuga/backend/events/queue.py`
2. Implement EventQueue class
3. Add unit tests

### Step 2: Create Event Processor
1. Create `src/cuga/backend/events/processor.py`
2. Implement EventProcessor class
3. Add unit tests

### Step 3: Create Webhook Routes
1. Create `src/cuga/backend/server/slack_routes.py`
2. Implement all three webhook endpoints
3. Add health check endpoint

### Step 4: Integrate with Main App
1. Modify `src/cuga/backend/server/main.py`
2. Add imports
3. Update AppState
4. Update lifespan
5. Include router

### Step 5: Test Integration
1. Start CUGA server
2. Start ngrok tunnel
3. Update Slack app URLs
4. Test each event type:
   - URL verification
   - App mention
   - Direct message
   - Slash command
   - Interaction (button click)

## Testing Strategy

### Unit Tests

1. **EventQueue Tests** (`tests/unit/test_event_queue.py`)
   - Test enqueue/dequeue
   - Test processor start/stop
   - Test error handling

2. **EventProcessor Tests** (`tests/unit/test_event_processor.py`)
   - Test event routing
   - Test Slack event processing
   - Test error handling
   - Test notification sending

3. **Webhook Routes Tests** (`tests/unit/test_slack_routes.py`)
   - Test signature verification
   - Test URL verification
   - Test event handling
   - Test error responses

### Integration Tests

1. **End-to-End Flow** (`tests/integration/test_slack_e2e.py`)
   - Mock Slack API
   - Send test events
   - Verify processing
   - Verify responses

## Security Considerations

1. **Signature Verification**: All requests verified with HMAC-SHA256
2. **Replay Attack Prevention**: Timestamp validation (5-minute window)
3. **Error Handling**: Don't expose internal errors to Slack
4. **Rate Limiting**: Consider adding rate limiting to webhooks
5. **Input Validation**: All payloads validated with Pydantic

## Monitoring

### Metrics to Track

- Events received (by type)
- Events processed (success/failure)
- Processing latency
- Queue depth
- Slack API errors
- Signature verification failures

### Logging

All events logged with:
- Event ID
- Event type
- Event name
- User ID
- Channel ID
- Processing status
- Error details (if any)

## Next Steps After Implementation

1. **CUGA Agent Integration**: Connect EventProcessor to actual CUGA agent
2. **Approval System Integration**: Handle approval interactions
3. **Redis Queue**: Replace in-memory queue with Redis for production
4. **Monitoring Dashboard**: Add metrics and monitoring
5. **Additional Event Sources**: GitHub, email, etc.

## Estimated Timeline

- **Step 1 (Event Queue)**: 1-2 hours
- **Step 2 (Event Processor)**: 2-3 hours
- **Step 3 (Webhook Routes)**: 2-3 hours
- **Step 4 (Integration)**: 1-2 hours
- **Step 5 (Testing)**: 2-3 hours

**Total**: 8-13 hours of development time

## Success Criteria

✅ Slack app can send events to CUGA
✅ Events are queued and processed asynchronously
✅ Responses are sent back to Slack
✅ All security checks pass
✅ Error handling works correctly
✅ Logging provides good visibility
✅ Tests pass and provide good coverage