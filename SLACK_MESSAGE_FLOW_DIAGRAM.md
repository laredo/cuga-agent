# Slack Message Flow Architecture

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SLACK WORKSPACE                                 │
│                                                                              │
│  User types: "@cuga help me with this task"                                │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    Slack API Server                           │          │
│  │  - Receives message                                           │          │
│  │  - Creates event payload                                      │          │
│  │  - Signs with HMAC-SHA256                                     │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                              │                                               │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               │ HTTPS POST
                               │ /webhooks/slack/events
                               │ Headers: X-Slack-Signature
                               │ Body: {type: "event_callback", event: {...}}
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NGROK (Development Only)                        │
│                                                                              │
│  Role: Secure tunnel from internet to localhost                            │
│  - Provides public HTTPS URL (e.g., https://abc123.ngrok.io)               │
│  - Forwards requests to localhost:8001                                      │
│  - Required because Slack needs a public URL                                │
│  - In production: Replace with actual public server                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │  Public URL: https://abc123.ngrok.io/webhooks/slack/events   │          │
│  │           ↓ forwards to ↓                                     │          │
│  │  Local URL: http://localhost:8001/webhooks/slack/events      │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                              │                                               │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               │ HTTP (local)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YOUR LOCAL MACHINE                                   │
│                    (CUGA Test Server - Port 8001)                           │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    FastAPI Application                              │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  1. Slack Webhook Routes (routes.py)                         │  │    │
│  │  │     POST /webhooks/slack/events                              │  │    │
│  │  │                                                               │  │    │
│  │  │  ✓ Verify HMAC-SHA256 signature                             │  │    │
│  │  │  ✓ Handle URL verification challenge                         │  │    │
│  │  │  ✓ Parse event payload                                       │  │    │
│  │  │  ✓ Create Event object                                       │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                              │                                       │    │
│  │                              │ Event object                          │    │
│  │                              ▼                                       │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  2. Event Queue (queue.py)                                   │  │    │
│  │  │     Async in-memory queue                                    │  │    │
│  │  │                                                               │  │    │
│  │  │  ✓ Add event to queue (non-blocking)                        │  │    │
│  │  │  ✓ Return 200 OK to Slack immediately                       │  │    │
│  │  │  ✓ Background processor picks up event                      │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                              │                                       │    │
│  │                              │ Background processing                 │    │
│  │                              ▼                                       │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  3. Event Processor (processor.py)                           │  │    │
│  │  │     Generic event router                                     │  │    │
│  │  │                                                               │  │    │
│  │  │  ✓ Determine event type (SLACK)                             │  │    │
│  │  │  ✓ Route to registered processor                            │  │    │
│  │  │  ✓ Handle session routing                                   │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                              │                                       │    │
│  │                              │ Route to Slack processor              │    │
│  │                              ▼                                       │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  4. Slack Event Processor (slack/processor.py)               │  │    │
│  │  │     Slack-specific event handling                            │  │    │
│  │  │                                                               │  │    │
│  │  │  ✓ Parse Slack event (app_mention, message, etc.)          │  │    │
│  │  │  ✓ Extract user, channel, text                              │  │    │
│  │  │  ✓ Create session context                                   │  │    │
│  │  │  ✓ Call CUGA agent (TODO: not yet connected)               │  │    │
│  │  │  ✓ Format response                                          │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                              │                                       │    │
│  │                              │ Response text                         │    │
│  │                              ▼                                       │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  5. Slack Notification Channel (notification_channel.py)    │  │    │
│  │  │     Send response back to Slack                              │  │    │
│  │  │                                                               │  │    │
│  │  │  ✓ Use Slack Web API client                                 │  │    │
│  │  │  ✓ Post message to channel                                  │  │    │
│  │  │  ✓ Handle threading (reply in thread)                       │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                              │                                       │    │
│  └──────────────────────────────┼───────────────────────────────────────┘    │
│                                 │ HTTPS POST                                 │
│                                 │ chat.postMessage                           │
└─────────────────────────────────┼──────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SLACK API SERVER                                     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │  Receives response from CUGA                                  │          │
│  │  Posts message in Slack channel                               │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                              │                                               │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SLACK WORKSPACE                                      │
│                                                                              │
│  User sees: "cuga: I can help you with that task. Here's what..."          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Slack Workspace (External)
**What it does:**
- User sends message mentioning @cuga
- Slack API server receives the message
- Creates event payload with metadata (user, channel, text, timestamp)
- Signs payload with HMAC-SHA256 using signing secret
- Sends HTTPS POST to configured webhook URL

**Key Data:**
```json
{
  "type": "event_callback",
  "event": {
    "type": "app_mention",
    "user": "U123456",
    "text": "@cuga help me with this task",
    "channel": "C789012",
    "ts": "1234567890.123456"
  }
}
```

### 2. ngrok (Development Tool)

**What it is:**
- Secure tunneling service
- Creates public HTTPS URL that forwards to localhost
- **NOT part of production deployment**

**Why it's needed:**
- Slack requires a **public HTTPS URL** for webhooks
- Your local machine (localhost:8001) is not accessible from the internet
- ngrok creates a bridge: `https://abc123.ngrok.io` → `http://localhost:8001`

**How it works:**
```
Internet → ngrok cloud → ngrok client (your machine) → localhost:8001
```

**In Production:**
- Replace ngrok with actual public server
- Deploy CUGA to cloud (AWS, Azure, GCP, etc.)
- Use real domain with SSL certificate
- Example: `https://cuga.yourcompany.com/webhooks/slack/events`

**ngrok Commands:**
```bash
# Start tunnel
ngrok http 8001

# Output shows:
# Forwarding: https://abc123.ngrok.io -> http://localhost:8001
```

### 3. Slack Webhook Routes (routes.py)

**Location:** `src/cuga/backend/integrations/slack/routes.py`

**Responsibilities:**
- Receive HTTPS POST from Slack
- Verify HMAC-SHA256 signature (security)
- Handle URL verification challenge (Slack setup)
- Parse event payload
- Create Event object
- Add to event queue
- Return 200 OK immediately (Slack requires response within 3 seconds)

**Endpoints:**
- `POST /webhooks/slack/events` - Main event endpoint
- `POST /webhooks/slack/commands` - Slash commands
- `POST /webhooks/slack/interactions` - Button clicks, modals
- `GET /webhooks/slack/health` - Health check

**Security:**
```python
# Verify signature to ensure request is from Slack
signature = request.headers.get("X-Slack-Signature")
timestamp = request.headers.get("X-Slack-Request-Timestamp")
body = await request.body()

# Compute HMAC-SHA256
computed_signature = compute_signature(signing_secret, timestamp, body)

if not hmac.compare_digest(signature, computed_signature):
    raise HTTPException(403, "Invalid signature")
```

### 4. Event Queue (queue.py)

**Location:** `src/cuga/backend/events/queue.py`

**Responsibilities:**
- Async in-memory queue (asyncio.Queue)
- Non-blocking event addition
- Background processor runs continuously
- Picks up events and processes them
- Error handling and retry logic
- Statistics tracking

**Why it's needed:**
- Slack requires response within 3 seconds
- Processing might take longer (AI inference, API calls)
- Queue allows immediate response, process later
- Prevents timeout errors

**Flow:**
```python
# 1. Add event (fast, non-blocking)
await event_queue.add_event(event)  # Returns immediately

# 2. Background processor (runs continuously)
async def process_events():
    while True:
        event = await queue.get()
        await processor.process_event(event)
```

### 5. Event Processor (processor.py)

**Location:** `src/cuga/backend/events/processor.py`

**Responsibilities:**
- Generic event router (works for any integration)
- Determines event type (SLACK, GITHUB, EMAIL, etc.)
- Routes to registered integration-specific processor
- Handles session routing (main vs isolated)
- Error logging and monitoring

**Registration Pattern:**
```python
# Register Slack processor
event_processor.register_processor(
    EventType.SLACK,
    slack_processor.process_event
)

# When event arrives, routes to correct processor
await event_processor.process_event(event)
```

### 6. Slack Event Processor (slack/processor.py)

**Location:** `src/cuga/backend/integrations/slack/processor.py`

**Responsibilities:**
- Slack-specific event handling
- Parse different event types (app_mention, message, reaction, etc.)
- Extract user, channel, text, thread info
- Create session context
- **TODO:** Call CUGA agent for AI response
- Format response for Slack
- Send via notification channel

**Event Types Handled:**
- `app_mention` - Bot mentioned in channel
- `message` - Direct message to bot
- `reaction_added` - User reacts to message
- `app_home_opened` - User opens bot's home tab

**Current Implementation:**
```python
# Placeholder - needs CUGA agent integration
response_text = f"Received your message: {text}"

# TODO: Replace with actual CUGA agent call
# from cuga.backend.cuga_graph.graph import DynamicAgentGraph
# agent = DynamicAgentGraph()
# response = await agent.process(text, session_context)
```

### 7. Slack Notification Channel (notification_channel.py)

**Location:** `src/cuga/backend/integrations/slack/notification_channel.py`

**Responsibilities:**
- Send responses back to Slack
- Use Slack Web API client
- Post messages to channels
- Handle threading (reply in thread vs new message)
- Format messages (text, blocks, attachments)
- Error handling for API calls

**Slack API Call:**
```python
from slack_sdk import WebClient

client = WebClient(token=SLACK_BOT_TOKEN)

response = client.chat_postMessage(
    channel=channel_id,
    text=response_text,
    thread_ts=thread_ts  # Reply in thread if provided
)
```

## Data Flow Summary

```
User Message
    ↓
Slack API (creates event, signs with HMAC)
    ↓
ngrok (tunnels to localhost) [DEV ONLY]
    ↓
Webhook Routes (verify signature, parse, queue)
    ↓ [immediate 200 OK response]
Event Queue (async, non-blocking)
    ↓ [background processing]
Event Processor (route by type)
    ↓
Slack Processor (handle Slack-specific logic)
    ↓
[TODO: CUGA Agent - AI processing]
    ↓
Notification Channel (send response)
    ↓
Slack API (post message)
    ↓
User sees response
```

## Timing

```
0ms    - User sends message in Slack
10ms   - Slack API receives, creates event
50ms   - Event reaches ngrok
60ms   - Webhook route receives event
65ms   - Signature verified
70ms   - Event added to queue
75ms   - 200 OK returned to Slack ✓ (within 3 second limit)
------- Background processing starts -------
100ms  - Event processor picks up event
150ms  - Slack processor handles event
200ms  - [TODO: CUGA agent processes - could take seconds]
500ms  - Response formatted
550ms  - Notification sent to Slack
600ms  - User sees response in Slack
```

## ngrok Role Clarification

### Development (Current Setup)
```
Slack → ngrok cloud → ngrok client → localhost:8001 → CUGA
```

**Why ngrok:**
- Slack needs public HTTPS URL
- localhost:8001 is not accessible from internet
- ngrok provides temporary public URL
- Free for development/testing

**Limitations:**
- URL changes each time you restart ngrok (free tier)
- Must update Slack app URLs each time
- Not suitable for production
- Can be slow (extra hop through ngrok cloud)

### Production (Future Deployment)
```
Slack → your-domain.com → CUGA server
```

**Replace ngrok with:**
- Cloud server (AWS EC2, Azure VM, GCP Compute Engine)
- Container platform (Kubernetes, ECS, Cloud Run)
- Serverless (AWS Lambda, Azure Functions)
- Platform-as-a-Service (Heroku, Railway, Render)

**Requirements:**
- Public IP address
- Domain name (optional but recommended)
- SSL certificate (Let's Encrypt is free)
- Firewall rules to allow HTTPS (port 443)

**Example Production Setup:**
```bash
# Deploy to cloud server
ssh user@your-server.com

# Install CUGA
git clone https://github.com/your-org/cuga-agent
cd cuga-agent
pip install -e .

# Configure environment
cp .env.slack.example .env.slack
# Edit .env.slack with production credentials

# Run with production server (not test server)
python -m cuga.cli.main

# Configure reverse proxy (nginx)
# Point domain to server
# Set up SSL with Let's Encrypt

# Update Slack app URLs
# https://your-domain.com/webhooks/slack/events
```

## Security Notes

1. **Signature Verification**: Every request from Slack is verified using HMAC-SHA256
2. **HTTPS Required**: Slack only sends to HTTPS URLs (ngrok provides this)
3. **Secrets Management**: Bot token and signing secret stored in `.env.slack`
4. **No Hardcoded Credentials**: All sensitive data in environment variables
5. **Request Validation**: Timestamp check prevents replay attacks

## Monitoring

**Statistics Endpoint:**
```bash
curl http://localhost:8001/stats
```

**Response:**
```json
{
  "event_queue": {
    "size": 0,
    "processed": 15,
    "failed": 0,
    "is_running": true
  },
  "session_manager": {
    "total_sessions": 3,
    "active_sessions": 2,
    "inactive_sessions": 1
  }
}
```

## Next Steps

1. **Test Current Setup**: Follow `QUICK_TEST.md` to test with ngrok
2. **Connect CUGA Agent**: Integrate AI processing in Slack processor
3. **Add Tests**: Unit and integration tests
4. **Deploy to Production**: Replace ngrok with real server
5. **Add Monitoring**: Logging, metrics, alerting
6. **Scale**: Add Redis queue, multiple workers, load balancing