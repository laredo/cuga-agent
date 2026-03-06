# CUGA Slack Integration

This package provides Slack integration for CUGA, enabling event-driven interactions through Slack's Events API, slash commands, and interactive components.

## Architecture

The Slack integration acts as an **adapter layer** that converts Slack events into CUGA's event system:

```
Slack → Webhook → SlackEventHandler → CUGA Event → Event Queue → CUGA Agent
                                                                      ↓
Slack ← SlackNotificationChannel ← Response ← Agent Processing ← Event Router
```

## Components

### 1. Models (`models.py`)
Pydantic models for Slack data structures:
- `SlackEventType`: Event type enum
- `SlackMessageType`: Message type enum
- `SlackUser`: User information
- `SlackChannel`: Channel information
- `SlackMessage`: Message data
- `SlackEvent`: Complete event payload
- `SlackInteraction`: Interactive component data

### 2. Client (`client.py`)
Async Slack API client wrapper:
- `verify_signature()`: Verify webhook signatures
- `send_message()`: Send messages to channels
- `update_message()`: Update existing messages
- `add_reaction()`: Add emoji reactions
- `get_user_info()`: Fetch user details
- `get_channel_info()`: Fetch channel details
- `upload_file()`: Upload files to Slack
- `open_modal()`: Open modal dialogs

### 3. Event Handler (`handler.py`)
Converts Slack events to CUGA events:
- `handle_event()`: Process Slack Events API callbacks
- `handle_slash_command()`: Process slash commands
- `handle_interaction()`: Process interactive components
- Enriches events with user/channel info
- Adds response routing information

### 4. Notification Channel (`notification_channel.py`)
Sends CUGA responses back to Slack:
- `send_response()`: Send agent responses
- `send_approval_request()`: Send approval requests with buttons
- `update_approval_message()`: Update approval status
- `send_thinking_indicator()`: Add thinking reaction
- `send_completion_indicator()`: Add completion reaction
- `send_error_indicator()`: Add error reaction

## Setup

### 1. Install Dependencies

```bash
pip install slack-sdk
```

### 2. Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From an app manifest"
3. Use the manifest from `slack-app-manifest.yaml`
4. Install the app to your workspace

### 3. Configure Environment

Copy `.env.slack.example` to `.env.slack` and fill in:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CLIENT_ID=your-client-id
SLACK_CLIENT_SECRET=your-client-secret
```

### 4. Set Up Webhooks

For local development, use ngrok:

```bash
# Install ngrok
brew install ngrok

# Start ngrok tunnel
ngrok http 8000

# Update Slack app URLs with ngrok URL
# Example: https://abc123.ngrok.io/webhooks/slack/events
```

For production, update the URLs in your Slack app settings to point to your deployed CUGA instance.

## Usage

### Initialize Slack Integration

```python
import os
from cuga.backend.integrations.slack import (
    SlackClient,
    SlackEventHandler,
    SlackNotificationChannel
)

# Initialize client
slack_client = SlackClient(
    bot_token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET")
)

# Initialize handler
slack_handler = SlackEventHandler(slack_client)

# Initialize notification channel
slack_notification = SlackNotificationChannel(slack_client)
```

### Handle Slack Events

```python
# In your webhook endpoint
async def handle_slack_event(payload: dict):
    # Convert to CUGA event
    event = await slack_handler.handle_event(payload)
    
    if event:
        # Enqueue for processing
        await event_queue.enqueue(event)
```

### Send Responses

```python
# After agent processes the event
await slack_notification.send_response(
    text="Here's the answer to your question...",
    channel=event.payload["response_channel"],
    thread_ts=event.payload["response_thread_ts"]
)
```

### Send Approval Requests

```python
# When approval is needed
approval_request = {
    "id": "req_123",
    "action": "Delete production database",
    "context": {"database": "prod_db", "user": "admin"}
}

await slack_notification.send_approval_request(
    approval_request=approval_request,
    channel=event.payload["response_channel"],
    thread_ts=event.payload["response_thread_ts"]
)
```

## Event Flow

### 1. App Mention (@CUGA)

```
User: @CUGA help me with this task
  ↓
Slack Events API → /webhooks/slack/events
  ↓
SlackEventHandler.handle_event()
  ↓
CUGA Event (type=slack, event_name=app_mention)
  ↓
Event Queue → Session Router → Agent
  ↓
Agent Response
  ↓
SlackNotificationChannel.send_response()
  ↓
Slack message in thread
```

### 2. Direct Message

```
User DM: Can you analyze this data?
  ↓
Slack Events API → /webhooks/slack/events
  ↓
SlackEventHandler.handle_event()
  ↓
CUGA Event (type=slack, event_name=direct_message)
  ↓
Event Queue → Session Router → Agent
  ↓
Agent Response
  ↓
SlackNotificationChannel.send_response()
  ↓
Slack DM reply
```

### 3. Slash Command

```
User: /cuga status
  ↓
Slack Commands → /webhooks/slack/commands
  ↓
SlackEventHandler.handle_slash_command()
  ↓
CUGA Event (type=slack, event_name=slash_command)
  ↓
Event Queue → Session Router → Agent
  ↓
Agent Response
  ↓
SlackNotificationChannel.send_response()
  ↓
Slack ephemeral message
```

### 4. Interactive Button (Approval)

```
User clicks: [Approve] button
  ↓
Slack Interactions → /webhooks/slack/interactions
  ↓
SlackEventHandler.handle_interaction()
  ↓
CUGA Event (type=slack, event_name=interaction)
  ↓
Event Queue → Approval Manager
  ↓
Approval processed
  ↓
SlackNotificationChannel.update_approval_message()
  ↓
Slack message updated with status
```

## Event Payload Structure

All Slack events include response routing information:

```python
{
    "type": "slack",
    "source": "webhook",
    "event_name": "app_mention",
    "payload": {
        "text": "user message",
        "user": {"id": "U123", "name": "John", "email": "john@example.com"},
        "channel": {"id": "C123", "name": "general"},
        "message_ts": "1234567890.123456",
        "thread_ts": "1234567890.123456",
        # Response routing
        "response_channel": "C123",
        "response_thread_ts": "1234567890.123456"
    },
    "metadata": {
        "session_target": "main",
        "slack_team_id": "T123",
        "slack_event_id": "Ev123"
    }
}
```

## Security

### Signature Verification

All webhook requests are verified using HMAC-SHA256:

```python
# Automatic in SlackClient
is_valid = slack_client.verify_signature(
    timestamp=request.headers["X-Slack-Request-Timestamp"],
    body=request.body,
    signature=request.headers["X-Slack-Signature"]
)
```

### Replay Attack Prevention

Requests older than 5 minutes are rejected automatically.

### Token Security

- Store tokens in environment variables or secrets manager
- Never commit tokens to version control
- Rotate tokens regularly
- Use least-privilege scopes

## Testing

### Unit Tests

```bash
pytest tests/unit/test_slack_integration.py
```

### Integration Tests

```bash
pytest tests/integration/test_slack_e2e.py
```

### Manual Testing with ngrok

1. Start CUGA with ngrok tunnel
2. Update Slack app URLs
3. Send test messages in Slack
4. Verify events are received and processed
5. Check responses appear in Slack

## Monitoring

### Metrics to Track

- Slack events received (by type)
- Event processing latency
- Response delivery success rate
- Approval request/response times
- Error rates by event type

### Logging

All Slack interactions are logged:

```python
logger.info("Slack event received", extra={
    "event_type": event.type,
    "event_id": event.id,
    "channel": event.payload.get("channel"),
    "user": event.payload.get("user")
})
```

## Troubleshooting

### Events Not Received

1. Check ngrok tunnel is running
2. Verify Slack app URLs are correct
3. Check signature verification
4. Review Slack app event subscriptions

### Responses Not Sent

1. Check bot token is valid
2. Verify bot has permission to post in channel
3. Check response_channel and response_thread_ts in event payload
4. Review Slack API error logs

### Approval Buttons Not Working

1. Verify interactivity is enabled in Slack app
2. Check interaction URL is correct
3. Verify button action_id matches handler
4. Review interaction payload structure

## Best Practices

1. **Always verify signatures** - Prevent unauthorized requests
2. **Use threads** - Keep conversations organized
3. **Add reactions** - Provide immediate feedback
4. **Handle errors gracefully** - Don't expose internal errors to users
5. **Rate limit** - Respect Slack API limits
6. **Log everything** - Essential for debugging
7. **Test thoroughly** - Use ngrok for local testing

## References

- [Slack API Documentation](https://api.slack.com/)
- [Slack Events API](https://api.slack.com/events-api)
- [Slack Interactive Components](https://api.slack.com/interactivity)
- [slack-sdk Documentation](https://slack.dev/python-slack-sdk/)
- [CUGA Event System](../events/README.md)

## Support

For issues or questions:
- GitHub Issues: https://github.com/cuga-project/cuga-agent/issues
- Documentation: https://cuga.dev/docs