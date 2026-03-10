# Complete Slack App Setup Guide for CUGA

## Understanding the Architecture

### Two Sides of the Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                         SLACK SIDE                              │
│  (Configuration - No Code Required)                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Slack App (created in Slack's UI)                          │
│     - Defines permissions (OAuth scopes)                        │
│     - Configures event subscriptions                            │
│     - Sets up slash commands                                    │
│     - Enables interactive components                            │
│     - Provides tokens (Bot Token, Signing Secret)               │
│                                                                 │
│  2. Slack Workspace                                             │
│     - Where the app is installed                                │
│     - Where users interact with @CUGA                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↕ HTTPS
┌─────────────────────────────────────────────────────────────────┐
│                         CUGA SIDE                               │
│  (Code - What We Implemented)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Slack Integration Code (✅ COMPLETE)                        │
│     - SlackClient: Sends messages to Slack                      │
│     - SlackEventHandler: Converts Slack events to CUGA events   │
│     - SlackNotificationChannel: Sends responses back            │
│                                                                 │
│  2. Webhook Endpoints (❌ MISSING - Need to implement)          │
│     - POST /webhooks/slack/events                               │
│     - POST /webhooks/slack/commands                             │
│     - POST /webhooks/slack/interactions                         │
│                                                                 │
│  3. Event Processing (✅ COMPLETE)                              │
│     - Event Queue                                               │
│     - Session Router                                            │
│     - CUGA Agent                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## What We Have vs What's Missing

### ✅ What We Implemented (Slack Integration Code)

1. **Slack Models** - Data structures for Slack events
2. **Slack Client** - Sends messages TO Slack
3. **Event Handler** - Converts Slack events to CUGA events
4. **Notification Channel** - Sends responses back to Slack
5. **App Manifest** - Template for creating the Slack app
6. **Documentation** - Complete setup guide

### ❌ What's Missing (Webhook Endpoints)

The **webhook endpoints** are the HTTP routes that:
- Receive events FROM Slack
- Verify signatures
- Call our SlackEventHandler
- Enqueue events for processing

**This is code that needs to be written**, not configuration.

### 🔧 What's Configuration (Slack App)

The **Slack app** is created in Slack's web UI:
- No code required
- Just configuration through Slack's interface
- Provides tokens and secrets
- Tells Slack where to send events (webhook URLs)

## Complete Setup Process

### Phase 1: Create Slack App (Configuration - 10 minutes)

#### Step 1: Go to Slack API Website

1. Visit https://api.slack.com/apps
2. Click **"Create New App"**
3. Choose **"From an app manifest"**
4. Select your workspace

#### Step 2: Use Our Manifest

1. Copy the contents of `slack-app-manifest.yaml`
2. Paste into the manifest editor
3. Click **"Next"** then **"Create"**

The manifest includes:
- App name: CUGA
- Bot user configuration
- OAuth scopes (permissions)
- Event subscriptions
- Slash commands
- Interactive components

#### Step 3: Get Your Credentials

After creating the app, you'll see:

1. **Basic Information** page:
   - Copy **Signing Secret** → Save for later
   - Copy **App ID** → Save for later

2. **OAuth & Permissions** page:
   - Click **"Install to Workspace"**
   - Authorize the app
   - Copy **Bot User OAuth Token** (starts with `xoxb-`) → Save for later

3. **App Credentials** section:
   - Copy **Client ID** → Save for later
   - Copy **Client Secret** → Save for later

#### Step 4: Configure Environment Variables

Create `.env.slack` file:

```bash
# Copy from .env.slack.example
cp .env.slack.example .env.slack

# Edit with your credentials
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
SLACK_CLIENT_ID=your-client-id-here
SLACK_CLIENT_SECRET=your-client-secret-here
SLACK_WORKSPACE_ID=T1234567890
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_APP_ID=A0AKALDSV8S
SLACK_APP_NAME=cuga
SLACK_APP_DESCRIPTION=A Slack App to connect to CUGA

# Optional: Enable CUGA integration for AI-powered responses (default: false)
# When enabled, messages will be processed by the CUGA AI agent
# When disabled, test responses will be sent
CUGA_SLACK_ENABLE=false
```

### Phase 2: Set Up Webhook URLs (Requires Running CUGA)

#### Option A: Local Development with ngrok (Recommended for Testing)

1. **Install ngrok**:
   ```bash
   brew install ngrok
   # or download from https://ngrok.com/download
   ```

2. **Start CUGA** (once webhook endpoints are implemented):
   ```bash
   cuga start
   # Assume it runs on http://localhost:8000
   ```

3. **Start ngrok tunnel**:
   ```bash
   ngrok http 8000
   ```

4. **Copy the ngrok URL**:
   ```
   Forwarding: https://abc123.ngrok.io -> http://localhost:8000
   ```

5. **Update Slack App URLs**:
   - Go to https://api.slack.com/apps
   - Select your CUGA app
   - Go to **Event Subscriptions**:
     - Request URL: `https://abc123.ngrok.io/webhooks/slack/events`
     - Click **"Save Changes"**
   - Go to **Interactivity & Shortcuts**:
     - Request URL: `https://abc123.ngrok.io/webhooks/slack/interactions`
     - Click **"Save Changes"**
   - Go to **Slash Commands**:
     - Edit each command
     - Request URL: `https://abc123.ngrok.io/webhooks/slack/commands`
     - Click **"Save"**

#### Option B: Production Deployment

1. **Deploy CUGA** to a server with a public domain:
   ```
   https://cuga.yourcompany.com
   ```

2. **Update Slack App URLs** (same as above but with your domain):
   - Event Subscriptions: `https://cuga.yourcompany.com/webhooks/slack/events`
   - Interactivity: `https://cuga.yourcompany.com/webhooks/slack/interactions`
   - Slash Commands: `https://cuga.yourcompany.com/webhooks/slack/commands`

### Phase 3: Implement Webhook Endpoints (Code - Still Needed)

This is the **missing piece** that needs to be implemented:

```python
# src/cuga/backend/api/webhooks/slack.py (NEEDS TO BE CREATED)

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import json
import logging
import os

from cuga.backend.integrations.slack import (
    SlackClient,
    SlackEventHandler,
    SlackNotificationChannel
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/slack", tags=["slack"])

# Initialize Slack components
slack_client = SlackClient(
    bot_token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)
slack_handler = SlackEventHandler(slack_client)

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
                # TODO: Enqueue event for processing
                # await event_queue.enqueue(event)
                logger.info(f"Received Slack event: {event.event_name}")
        except Exception as e:
            logger.error(f"Error handling Slack event: {e}")
    
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
    
    # Verify signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    from urllib.parse import parse_qs
    payload = {k: v[0] for k, v in parse_qs(body_str).items()}
    
    try:
        event = await slack_handler.handle_slash_command(payload)
        # TODO: Enqueue event
        # await event_queue.enqueue(event)
        
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
    
    # Verify signature
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
        # TODO: Enqueue event
        # await event_queue.enqueue(event)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling interaction: {e}")
        return {"ok": False, "error": str(e)}
```

### Phase 4: Test the Integration

#### Test 1: URL Verification

When you first set the Event Subscriptions URL, Slack sends a challenge:

```json
{
  "type": "url_verification",
  "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"
}
```

Your endpoint must respond with:
```json
{
  "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"
}
```

If this works, Slack will show a green checkmark ✅

#### Test 2: App Mention

1. In Slack, go to a channel where CUGA is added
2. Type: `@CUGA hello`
3. Check CUGA logs for:
   ```
   INFO: Received Slack event: app_mention
   ```

#### Test 3: Direct Message

1. In Slack, open a DM with CUGA
2. Type: `hello`
3. Check CUGA logs for:
   ```
   INFO: Received Slack event: direct_message
   ```

#### Test 4: Slash Command

1. In any Slack channel
2. Type: `/cuga status`
3. Should see: "Processing your request..."
4. Check CUGA logs for:
   ```
   INFO: Received Slack event: slash_command
   ```

#### Test 5: Approval Button

1. Trigger an action that requires approval
2. CUGA sends message with [Approve] [Reject] buttons
3. Click [Approve]
4. Check CUGA logs for:
   ```
   INFO: Received Slack event: interaction
   ```

## Summary: What Covers the Gap?

### ✅ Slack App (Configuration)

**Purpose**: Tells Slack about CUGA and where to send events

**What it does**:
- Defines permissions (what CUGA can do in Slack)
- Configures event subscriptions (what events to send)
- Provides tokens (for authentication)
- Sets webhook URLs (where to send events)

**Status**: ✅ Template provided (`slack-app-manifest.yaml`)

### ❌ Webhook Endpoints (Code)

**Purpose**: Receives events FROM Slack and processes them

**What it does**:
- Listens for HTTP POST requests from Slack
- Verifies signatures (security)
- Converts Slack events to CUGA events
- Enqueues events for processing

**Status**: ❌ Needs to be implemented (code shown above)

### ✅ Slack Integration Code

**Purpose**: Handles Slack-specific logic

**What it does**:
- Converts between Slack format and CUGA format
- Sends messages back to Slack
- Handles approval buttons
- Manages reactions

**Status**: ✅ Complete and committed

## The Complete Flow

```
1. User types "@CUGA help" in Slack
   ↓
2. Slack App receives the message
   ↓
3. Slack sends HTTP POST to: https://your-domain.com/webhooks/slack/events
   ↓
4. Webhook Endpoint (❌ MISSING):
   - Verifies signature
   - Calls SlackEventHandler (✅ IMPLEMENTED)
   - Enqueues CUGA event
   ↓
5. CUGA Agent processes event (✅ IMPLEMENTED)
   ↓
6. Agent generates response
   ↓
7. SlackNotificationChannel (✅ IMPLEMENTED):
   - Formats response
   - Sends to Slack API
   ↓
8. User sees response in Slack
```

## Next Steps

1. **Create Slack App** (10 minutes) - Follow Phase 1 above
2. **Implement Webhook Endpoints** (1-2 hours) - Write the FastAPI routes
3. **Set up ngrok** (5 minutes) - For local testing
4. **Update Slack App URLs** (5 minutes) - Point to ngrok/production
5. **Test Integration** (30 minutes) - Verify all event types work

## Questions?

- **Q: Do I need to write code for the Slack app?**
  - A: No, the Slack app is pure configuration through Slack's web UI

- **Q: What code is missing?**
  - A: The webhook endpoints (FastAPI routes) that receive events from Slack

- **Q: Can I test without implementing webhooks?**
  - A: No, Slack needs a public URL to send events to

- **Q: What's the fastest way to test?**
  - A: Implement the webhook endpoints, use ngrok for local testing

- **Q: Is the Slack integration code complete?**
  - A: Yes! All Slack-specific logic is implemented. Only the generic webhook infrastructure is missing.