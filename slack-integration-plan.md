# CUGA-Slack Integration Plan

## Overview

This document outlines the complete plan for integrating CUGA with Slack, enabling event-driven interactions through Slack events, commands, and interactive components.

## Architecture Overview

```
Slack Workspace
    ↓ (Events/Commands/Interactions)
Slack API (Events API, Slash Commands, Interactive Components)
    ↓ (HTTPS Webhooks)
CUGA Webhook Endpoint (FastAPI)
    ↓ (Event Creation)
CUGA Event Queue
    ↓ (Event Processing)
CUGA Agent (LangGraph)
    ↓ (Responses)
Slack API (Web API)
    ↓ (Messages/Updates)
Slack Workspace
```

## Phase 1: Slack App Configuration

### 1.1 Create Slack App

**App Manifest** (slack-app-manifest.yaml):
```yaml
display_information:
  name: CUGA
  description: Generalist AI Agent for Slack
  background_color: "#1e3a8a"
  long_description: "CUGA is an event-driven AI agent that can help with tasks, answer questions, and automate workflows in your Slack workspace."

features:
  app_home:
    home_tab_enabled: true
    messages_tab_enabled: true
    messages_tab_read_only_enabled: false
  bot_user:
    display_name: CUGA
    always_online: true
  slash_commands:
    - command: /cuga
      description: "Interact with CUGA agent"
      usage_hint: "[your request]"
      should_escape: false
    - command: /cuga-approve
      description: "Approve a pending action"
      usage_hint: "[approval_id]"
      should_escape: false
    - command: /cuga-reject
      description: "Reject a pending action"
      usage_hint: "[approval_id] [reason]"
      should_escape: false
    - command: /cuga-status
      description: "Check CUGA status and pending approvals"
      usage_hint: ""
      should_escape: false

oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - channels:history
      - channels:read
      - chat:write
      - chat:write.public
      - commands
      - files:read
      - files:write
      - groups:history
      - groups:read
      - im:history
      - im:read
      - im:write
      - links:read
      - links:write
      - reactions:read
      - reactions:write
      - users:read
      - users:read.email

settings:
  event_subscriptions:
    request_url: https://your-domain.com/webhooks/slack/events
    bot_events:
      - app_mention
      - message.channels
      - message.groups
      - message.im
      - reaction_added
      - reaction_removed
  interactivity:
    is_enabled: true
    request_url: https://your-domain.com/webhooks/slack/interactions
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

### 1.2 Required Slack Credentials

Store these securely (environment variables or Vault):

```bash
# OAuth & Permissions
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token  # For Socket Mode (optional)

# Signing Secret (for webhook verification)
SLACK_SIGNING_SECRET=your-signing-secret

# OAuth Client Credentials (for installation)
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret

# Workspace Configuration
SLACK_WORKSPACE_ID=T1234567890
SLACK_TEAM_DOMAIN=your-workspace
```

### 1.3 Slack App Permissions

**Bot Token Scopes**:
- `app_mentions:read` - Detect @mentions
- `channels:history` - Read channel messages
- `channels:read` - View channel info
- `chat:write` - Send messages
- `chat:write.public` - Send messages to channels CUGA isn't in
- `commands` - Add slash commands
- `files:read` - Access files shared in messages
- `files:write` - Upload files
- `groups:history` - Read private channel messages
- `groups:read` - View private channel info
- `im:history` - Read DM messages
- `im:read` - View DM info
- `im:write` - Send DMs
- `reactions:read` - View reactions
- `reactions:write` - Add reactions
- `users:read` - View user info
- `users:read.email` - View user emails

## Phase 2: CUGA Backend Implementation

### 2.1 Slack Event Models

**File**: `src/cuga/backend/integrations/slack/models.py`

```python
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class SlackEventType(str, Enum):
    """Slack event types"""
    APP_MENTION = "app_mention"
    MESSAGE = "message"
    REACTION_ADDED = "reaction_added"
    REACTION_REMOVED = "reaction_removed"
    SLASH_COMMAND = "slash_command"
    INTERACTION = "interaction"
    
class SlackMessageType(str, Enum):
    """Slack message types"""
    CHANNEL = "channel"
    GROUP = "group"  # Private channel
    IM = "im"  # Direct message
    MPIM = "mpim"  # Multi-person DM

class SlackUser(BaseModel):
    """Slack user information"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: str
    username: Optional[str] = None
    real_name: Optional[str] = None
    email: Optional[str] = None
    is_bot: bool = False

class SlackChannel(BaseModel):
    """Slack channel information"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: str
    name: Optional[str] = None
    is_private: bool = False
    is_im: bool = False

class SlackMessage(BaseModel):
    """Slack message"""
    model_config = ConfigDict(use_enum_values=True)
    
    text: str
    user: str
    ts: str  # Timestamp (message ID)
    channel: str
    channel_type: SlackMessageType
    thread_ts: Optional[str] = None  # Thread parent timestamp
    files: List[Dict[str, Any]] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    blocks: List[Dict[str, Any]] = Field(default_factory=list)

class SlackEvent(BaseModel):
    """Slack event payload"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: SlackEventType
    event_id: str
    event_time: datetime
    team_id: str
    user: Optional[SlackUser] = None
    channel: Optional[SlackChannel] = None
    message: Optional[SlackMessage] = None
    reaction: Optional[str] = None
    command: Optional[str] = None
    response_url: Optional[str] = None
    trigger_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SlackInteraction(BaseModel):
    """Slack interactive component"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: Literal["block_actions", "view_submission", "shortcut"]
    user: SlackUser
    channel: Optional[SlackChannel] = None
    message: Optional[SlackMessage] = None
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    view: Optional[Dict[str, Any]] = None
    response_url: Optional[str] = None
    trigger_id: str
```

### 2.2 Slack Client

**File**: `src/cuga/backend/integrations/slack/client.py`

```python
import asyncio
import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
import logging

logger = logging.getLogger(__name__)

class SlackClient:
    """Async Slack client wrapper"""
    
    def __init__(self, bot_token: str, signing_secret: str):
        self.client = AsyncWebClient(token=bot_token)
        self.signing_secret = signing_secret
        
    def verify_signature(self, timestamp: str, body: str, signature: str) -> bool:
        """Verify Slack request signature"""
        # Prevent replay attacks (timestamp must be within 5 minutes)
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
            
        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body}"
        expected_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send a message to a channel"""
        try:
            response = await self.client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts,
                blocks=blocks,
                attachments=attachments
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Error sending message: {e.response['error']}")
            raise
    
    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Update an existing message"""
        try:
            response = await self.client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Error updating message: {e.response['error']}")
            raise
    
    async def add_reaction(self, channel: str, timestamp: str, emoji: str):
        """Add a reaction to a message"""
        try:
            await self.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
        except SlackApiError as e:
            logger.error(f"Error adding reaction: {e.response['error']}")
            raise
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information"""
        try:
            response = await self.client.users_info(user=user_id)
            return response.data["user"]
        except SlackApiError as e:
            logger.error(f"Error getting user info: {e.response['error']}")
            raise
    
    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel information"""
        try:
            response = await self.client.conversations_info(channel=channel_id)
            return response.data["channel"]
        except SlackApiError as e:
            logger.error(f"Error getting channel info: {e.response['error']}")
            raise
    
    async def upload_file(
        self,
        channels: List[str],
        file: bytes,
        filename: str,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a file to Slack"""
        try:
            response = await self.client.files_upload_v2(
                channels=channels,
                file=file,
                filename=filename,
                title=title,
                initial_comment=initial_comment,
                thread_ts=thread_ts
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Error uploading file: {e.response['error']}")
            raise
    
    async def open_modal(self, trigger_id: str, view: Dict[str, Any]) -> Dict[str, Any]:
        """Open a modal dialog"""
        try:
            response = await self.client.views_open(
                trigger_id=trigger_id,
                view=view
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Error opening modal: {e.response['error']}")
            raise
```

### 2.3 Slack Event Handler

**File**: `src/cuga/backend/integrations/slack/handler.py`

```python
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from cuga.backend.events.models import Event, EventType, EventSource
from cuga.backend.integrations.slack.models import (
    SlackEvent, SlackEventType, SlackMessage, SlackUser, SlackChannel
)
from cuga.backend.integrations.slack.client import SlackClient

logger = logging.getLogger(__name__)

class SlackEventHandler:
    """Handles Slack events and converts them to CUGA events"""
    
    def __init__(self, slack_client: SlackClient):
        self.slack_client = slack_client
    
    async def handle_event(self, payload: Dict[str, Any]) -> Optional[Event]:
        """Convert Slack event to CUGA event"""
        event_type = payload.get("event", {}).get("type")
        
        if event_type == "app_mention":
            return await self._handle_app_mention(payload)
        elif event_type == "message":
            return await self._handle_message(payload)
        elif event_type == "reaction_added":
            return await self._handle_reaction(payload, added=True)
        elif event_type == "reaction_removed":
            return await self._handle_reaction(payload, added=False)
        else:
            logger.warning(f"Unhandled Slack event type: {event_type}")
            return None
    
    async def _handle_app_mention(self, payload: Dict[str, Any]) -> Event:
        """Handle @mention of CUGA"""
        event_data = payload["event"]
        
        # Get user and channel info
        user_info = await self.slack_client.get_user_info(event_data["user"])
        channel_info = await self.slack_client.get_channel_info(event_data["channel"])
        
        # Create CUGA event
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="app_mention",
            payload={
                "text": event_data["text"],
                "user": {
                    "id": user_info["id"],
                    "name": user_info.get("real_name", user_info.get("name")),
                    "email": user_info.get("profile", {}).get("email")
                },
                "channel": {
                    "id": channel_info["id"],
                    "name": channel_info.get("name"),
                    "is_private": channel_info.get("is_private", False)
                },
                "message_ts": event_data["ts"],
                "thread_ts": event_data.get("thread_ts"),
                "files": event_data.get("files", [])
            },
            metadata={
                "session_target": "main",  # Use main session for context
                "slack_team_id": payload["team_id"],
                "slack_event_id": payload["event_id"]
            }
        )
    
    async def _handle_message(self, payload: Dict[str, Any]) -> Optional[Event]:
        """Handle direct message to CUGA"""
        event_data = payload["event"]
        
        # Ignore bot messages and message changes
        if event_data.get("subtype") or event_data.get("bot_id"):
            return None
        
        # Only handle DMs (channel_type == "im")
        channel_type = event_data.get("channel_type")
        if channel_type != "im":
            return None
        
        user_info = await self.slack_client.get_user_info(event_data["user"])
        
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="direct_message",
            payload={
                "text": event_data["text"],
                "user": {
                    "id": user_info["id"],
                    "name": user_info.get("real_name", user_info.get("name")),
                    "email": user_info.get("profile", {}).get("email")
                },
                "channel": event_data["channel"],
                "message_ts": event_data["ts"],
                "thread_ts": event_data.get("thread_ts"),
                "files": event_data.get("files", [])
            },
            metadata={
                "session_target": "main",
                "slack_team_id": payload["team_id"],
                "slack_event_id": payload["event_id"]
            }
        )
    
    async def _handle_reaction(
        self, payload: Dict[str, Any], added: bool
    ) -> Event:
        """Handle reaction added/removed"""
        event_data = payload["event"]
        
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="reaction_added" if added else "reaction_removed",
            payload={
                "reaction": event_data["reaction"],
                "user": event_data["user"],
                "item": event_data["item"],
                "item_user": event_data.get("item_user")
            },
            metadata={
                "session_target": "isolated",  # Reactions are independent
                "slack_team_id": payload["team_id"],
                "slack_event_id": payload["event_id"]
            }
        )
    
    async def handle_slash_command(self, payload: Dict[str, Any]) -> Event:
        """Handle slash command"""
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="slash_command",
            payload={
                "command": payload["command"],
                "text": payload.get("text", ""),
                "user_id": payload["user_id"],
                "user_name": payload["user_name"],
                "channel_id": payload["channel_id"],
                "channel_name": payload.get("channel_name"),
                "response_url": payload["response_url"],
                "trigger_id": payload["trigger_id"]
            },
            metadata={
                "session_target": "main",
                "slack_team_id": payload["team_id"]
            }
        )
    
    async def handle_interaction(self, payload: Dict[str, Any]) -> Event:
        """Handle interactive component (button, select, etc.)"""
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="interaction",
            payload={
                "type": payload["type"],
                "user": payload["user"],
                "channel": payload.get("channel"),
                "message": payload.get("message"),
                "actions": payload.get("actions", []),
                "view": payload.get("view"),
                "response_url": payload.get("response_url"),
                "trigger_id": payload["trigger_id"]
            },
            metadata={
                "session_target": "main",
                "slack_team_id": payload["team"]["id"]
            }
        )
```

### 2.4 FastAPI Webhook Endpoints

**File**: `src/cuga/backend/api/webhooks/slack.py`

```python
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import json
import logging
from cuga.backend.integrations.slack.client import SlackClient
from cuga.backend.integrations.slack.handler import SlackEventHandler
from cuga.backend.events.queue import EventQueue  # To be implemented

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/slack", tags=["slack"])

# Initialize Slack client and handler (from config)
slack_client = SlackClient(
    bot_token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)
slack_handler = SlackEventHandler(slack_client)
event_queue = EventQueue()  # To be implemented

@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack Events API callbacks"""
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify Slack signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = json.loads(body_str)
    
    # Handle URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}
    
    # Handle event
    if payload.get("type") == "event_callback":
        try:
            event = await slack_handler.handle_event(payload)
            if event:
                await event_queue.enqueue(event)
                logger.info(f"Enqueued Slack event: {event.event_name}")
        except Exception as e:
            logger.error(f"Error handling Slack event: {e}")
            # Return 200 to prevent retries for application errors
            return {"ok": True}
    
    return {"ok": True}

@router.post("/commands")
async def slack_commands(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack slash commands"""
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify Slack signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    from urllib.parse import parse_qs
    payload = {k: v[0] for k, v in parse_qs(body_str).items()}
    
    try:
        event = await slack_handler.handle_slash_command(payload)
        await event_queue.enqueue(event)
        
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
    """Handle Slack interactive components"""
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify Slack signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    from urllib.parse import parse_qs
    form_data = parse_qs(body_str)
    payload = json.loads(form_data["payload"][0])
    
    try:
        event = await slack_handler.handle_interaction(payload)
        await event_queue.enqueue(event)
        
        # Immediate acknowledgment
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling interaction: {e}")
        return {"ok": False, "error": str(e)}
```

## Phase 3: Integration with CUGA's Event System

### 3.1 Event Queue Integration

The Slack integration simply creates CUGA Events and enqueues them. CUGA's existing event-driven system handles everything else:

```python
# In webhook endpoints (already shown in Phase 2.4)
event = await slack_handler.handle_event(payload)
if event:
    await event_queue.enqueue(event)  # CUGA's existing event queue
    # That's it! CUGA processes the event through its existing system
```

### 3.2 How CUGA Processes Slack Events

**No changes needed to CUGA!** The existing event system handles it:

1. **Event Queue** receives Slack event (type="slack")
2. **Session Router** routes to main/isolated session based on metadata
3. **LangGraph Agent** processes the event through existing nodes
4. **Agent generates response** using existing tools and logic
5. **Response needs to go back to Slack** - this is the only new part

### 3.3 Slack Notification Channel

Add Slack as a notification channel for the approval system:

**File**: `src/cuga/backend/integrations/slack/notification_channel.py`

```python
from typing import Dict, Any
from cuga.backend.integrations.slack.client import SlackClient
import logging

logger = logging.getLogger(__name__)

class SlackNotificationChannel:
    """Slack notification channel for approvals and responses"""
    
    def __init__(self, slack_client: SlackClient):
        self.slack_client = slack_client
    
    async def send_approval_request(
        self,
        approval_request: Dict[str, Any],
        channel: str,
        thread_ts: str = None
    ):
        """Send approval request to Slack with interactive buttons"""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Approval Required*\n\n{approval_request['action']}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Request ID: `{approval_request['id']}`"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "action_id": "approve_action",
                        "value": approval_request['id']
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "action_id": "reject_action",
                        "value": approval_request['id']
                    }
                ]
            }
        ]
        
        await self.slack_client.send_message(
            channel=channel,
            text=f"Approval required: {approval_request['action']}",
            thread_ts=thread_ts,
            blocks=blocks
        )
    
    async def send_response(
        self,
        text: str,
        channel: str,
        thread_ts: str = None
    ):
        """Send agent response to Slack"""
        # Format response with blocks for better UX
        blocks = self._format_response_blocks(text)
        
        await self.slack_client.send_message(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            blocks=blocks
        )
    
    def _format_response_blocks(self, text: str) -> list:
        """Format text into Slack blocks"""
        max_length = 3000
        blocks = []
        
        if len(text) <= max_length:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            })
        else:
            # Split into chunks
            chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            for chunk in chunks:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": chunk}
                })
        
        return blocks
```

### 3.4 Register Slack as Notification Channel

In CUGA's approval system configuration:

```python
from cuga.backend.events.approval_system import ApprovalManager
from cuga.backend.integrations.slack.notification_channel import SlackNotificationChannel

# Initialize
approval_manager = ApprovalManager()
slack_channel = SlackNotificationChannel(slack_client)

# Register Slack as a notification channel
approval_manager.register_notification_channel("slack", slack_channel)
```

### 3.5 Event Payload Structure

Slack events include response routing information:

```python
Event(
    type=EventType.SLACK,
    source=EventSource.WEBHOOK,
    event_name="app_mention",
    payload={
        "text": "Hey @CUGA, help me with...",
        "user": {"id": "U123", "name": "John"},
        "channel": {"id": "C123", "name": "general"},
        "message_ts": "1234567890.123456",
        "thread_ts": "1234567890.123456",  # For threading
        # Response routing info
        "response_channel": "C123",
        "response_thread_ts": "1234567890.123456"
    },
    metadata={
        "session_target": "main",
        "slack_team_id": "T123",
        "slack_event_id": "Ev123"
    }
)
```

CUGA's agent can read `payload.response_channel` and `payload.response_thread_ts` to know where to send the response.

## Phase 4: Deployment & Configuration

### 4.1 Environment Configuration

**File**: `.env.slack`

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret
SLACK_WORKSPACE_ID=T1234567890

# Webhook URLs (update after deployment)
SLACK_WEBHOOK_BASE_URL=https://your-domain.com
SLACK_EVENTS_URL=${SLACK_WEBHOOK_BASE_URL}/webhooks/slack/events
SLACK_COMMANDS_URL=${SLACK_WEBHOOK_BASE_URL}/webhooks/slack/commands
SLACK_INTERACTIONS_URL=${SLACK_WEBHOOK_BASE_URL}/webhooks/slack/interactions

# Feature Flags
SLACK_ENABLE_THREADS=true
SLACK_ENABLE_REACTIONS=true
SLACK_ENABLE_FILE_UPLOADS=true
SLACK_ENABLE_APPROVALS=true
```

### 4.2 Dependencies

**Add to pyproject.toml**:

```toml
[project.dependencies]
slack-sdk = "^3.27.0"
```

### 4.3 Ngrok for Local Development

```bash
# Install ngrok
brew install ngrok

# Start ngrok tunnel
ngrok http 8000

# Update Slack app URLs with ngrok URL
# Example: https://abc123.ngrok.io/webhooks/slack/events
```

## Phase 5: Testing

### 5.1 Unit Tests

**File**: `tests/unit/test_slack_integration.py`

```python
import pytest
from cuga.backend.integrations.slack.models import SlackEvent, SlackEventType
from cuga.backend.integrations.slack.handler import SlackEventHandler
from cuga.backend.integrations.slack.client import SlackClient

@pytest.mark.asyncio
async def test_app_mention_handling():
    """Test handling of @mention events"""
    # Test implementation
    pass

@pytest.mark.asyncio
async def test_slash_command_handling():
    """Test handling of slash commands"""
    # Test implementation
    pass

@pytest.mark.asyncio
async def test_signature_verification():
    """Test Slack signature verification"""
    # Test implementation
    pass
```

### 5.2 Integration Tests

**File**: `tests/integration/test_slack_e2e.py`

```python
import pytest
from fastapi.testclient import TestClient

@pytest.mark.integration
async def test_slack_event_to_agent_response():
    """Test complete flow from Slack event to agent response"""
    # Test implementation
    pass
```

## Phase 6: Monitoring & Observability

### 6.1 Metrics

- Slack events received (by type)
- Event processing latency
- Response delivery success rate
- Approval request/response times
- Error rates by event type

### 6.2 Logging

```python
logger.info("Slack event received", extra={
    "event_type": event.type,
    "event_id": event.id,
    "channel": event.payload.get("channel"),
    "user": event.payload.get("user")
})
```

## Implementation Checklist

- [ ] Create Slack app in workspace
- [ ] Configure app manifest and permissions
- [ ] Implement Slack models
- [ ] Implement Slack client
- [ ] Implement event handler
- [ ] Implement webhook endpoints
- [ ] Implement response handler
- [ ] Integrate with LangGraph
- [ ] Add environment configuration
- [ ] Install dependencies
- [ ] Set up ngrok for local testing
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Deploy to production
- [ ] Update Slack app URLs
- [ ] Test end-to-end flow
- [ ] Set up monitoring
- [ ] Document usage

## Security Considerations

1. **Signature Verification**: Always verify Slack signatures
2. **Token Security**: Store tokens in Vault/secrets manager
3. **Rate Limiting**: Implement rate limiting on webhooks
4. **Input Validation**: Validate all Slack payloads
5. **Error Handling**: Don't expose internal errors to Slack
6. **Audit Logging**: Log all Slack interactions

## Next Steps

After Slack integration is complete:
1. Add support for Slack workflows
2. Implement Slack app home tab
3. Add rich message formatting (cards, modals)
4. Implement file handling
5. Add support for Slack Connect (external workspaces)
6. Implement Slack app distribution

---

**Status**: Ready for implementation
**Priority**: High
**Estimated Effort**: 2-3 days