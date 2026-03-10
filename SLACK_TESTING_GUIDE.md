# Slack Integration Testing Guide

This guide explains how to test the Slack webhook integration for CUGA.

## Prerequisites

1. **Slack App Created**: You should have already created a Slack app following `SLACK_APP_SETUP_GUIDE.md`
2. **Environment Variables**: Your `.env.slack` file should contain:
   ```bash
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_SIGNING_SECRET=your-signing-secret
   ```
3. **ngrok Installed**: Download from https://ngrok.com/download

## Testing Options

### Option 1: Standalone Test Server (Recommended for Initial Testing)

This option runs a minimal FastAPI server with just the Slack webhooks, making it easier to test and debug.

#### Step 1: Start the Test Server

```bash
# From the project root
python src/system_tests/e2e/test_slack_integration.py
```

You should see output like:
```
🚀 Starting Slack webhook test server...
✅ Event queue started
✅ Slack integration initialized
   Bot Token: xoxb-1234567890123-...
   Signing Secret: a1b2c3d4e5f6g7h8i9...
🌐 Server ready at http://localhost:8001
📝 Endpoints:
   - POST /webhooks/slack/events
   - POST /webhooks/slack/commands
   - POST /webhooks/slack/interactions
   - GET  /webhooks/slack/health
```

#### Step 2: Start ngrok

In a **separate terminal**:

```bash
ngrok http 8001
```

You'll see output like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8001
```

Copy the `https://abc123.ngrok.io` URL.

#### Step 3: Update Slack App URLs

1. Go to https://api.slack.com/apps
2. Select your CUGA app
3. Go to **Event Subscriptions**:
   - Request URL: `https://abc123.ngrok.io/webhooks/slack/events`
   - Click "Save Changes"
4. Go to **Slash Commands**:
   - Edit each command's Request URL to: `https://abc123.ngrok.io/webhooks/slack/commands`
5. Go to **Interactivity & Shortcuts**:
   - Request URL: `https://abc123.ngrok.io/webhooks/slack/interactions`

#### Step 4: Test the Integration

**Test 1: Health Check**
```bash
curl https://abc123.ngrok.io/webhooks/slack/health
```

Expected response:
```json
{
  "status": "healthy",
  "slack_configured": true,
  "timestamp": "2026-03-09T03:30:00.000Z"
}
```

**Test 2: Mention the Bot in Slack**

In your Slack workspace:
1. Go to a channel where the bot is added
2. Type: `@cuga hello!`
3. Watch the test server logs for activity

Expected logs:
```
INFO: Received Slack event: app_mention
INFO: Processing event: <event_id>
INFO: Sending response to Slack channel
```

**Test 3: Use a Slash Command**

In Slack:
1. Type: `/cuga help`
2. Watch the test server logs

Expected logs:
```
INFO: Received Slack command: /cuga
INFO: Processing command with text: help
```

**Test 4: Check Statistics**

```bash
curl http://localhost:8001/stats
```

Expected response:
```json
{
  "event_queue": {
    "size": 0,
    "processed": 5,
    "failed": 0,
    "is_running": true
  },
  "session_manager": {
    "total_sessions": 2,
    "active_sessions": 2,
    "inactive_sessions": 0,
    "main_session_active": true,
    "isolated_sessions": 1
  }
}
```

### Option 2: Full CUGA Server Integration

This option integrates the Slack webhooks into the main CUGA server.

#### Step 1: Modify main.py

Add the following to `src/cuga/backend/server/main.py`:

**At the top with other imports:**
```python
from cuga.backend.events.queue import EventQueue
from cuga.backend.events.processor import EventProcessor
from cuga.backend.events.session_management import SessionRouter, SessionManager
from cuga.backend.events.models import EventType
from cuga.backend.integrations.slack import (
    router as slack_router,
    initialize_slack,
    get_slack_processor,
)
```

**In the AppState class `__init__` method:**
```python
self.event_queue: Optional[EventQueue] = None
self.event_processor: Optional[EventProcessor] = None
self.session_manager: Optional[SessionManager] = None
self.session_router: Optional[SessionRouter] = None
```

**In the `lifespan` function, after line 380 (after `await manage_save_reuse_server()`):**
```python
# Initialize event system for webhooks
app_state.event_queue = EventQueue(max_size=1000)
app_state.session_manager = SessionManager()
app_state.session_router = SessionRouter(manager=app_state.session_manager)
app_state.event_processor = EventProcessor(app_state.session_router)
app_state.event_queue.start_processor(app_state.event_processor.process_event)
logger.info("✅ Event system initialized")

# Initialize Slack integration if configured
if initialize_slack(app_state.event_queue):
    slack_processor = get_slack_processor()
    if slack_processor:
        app_state.event_processor.register_processor(
            EventType.SLACK,
            slack_processor.process_event
        )
        logger.success("✅ Slack integration initialized")
else:
    logger.info("Slack integration not configured (set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET)")
```

**In the `lifespan` function shutdown section (before the final yield):**
```python
# Shutdown event queue
if app_state.event_queue:
    await app_state.event_queue.stop()
    logger.info("Event queue stopped")
```

**After creating the FastAPI app (around line 2800):**
```python
# Include Slack webhook router
app.include_router(slack_router)
```

#### Step 2: Start CUGA

```bash
# From the project root
python -m cuga.cli.main
```

#### Step 3: Start ngrok

```bash
ngrok http 8000  # Note: port 8000 for main CUGA server
```

#### Step 4: Update Slack App URLs

Same as Option 1, but use port 8000 instead of 8001.

#### Step 5: Test

Same tests as Option 1, but the bot will now have access to the full CUGA agent capabilities.

## Troubleshooting

### Issue: "Slack integration not configured"

**Solution**: Check that your `.env.slack` file exists and contains valid credentials:
```bash
cat .env.slack
```

### Issue: "Signature verification failed"

**Solution**: 
1. Verify your `SLACK_SIGNING_SECRET` matches the one in your Slack app settings
2. Check that ngrok is forwarding to the correct port
3. Ensure your system clock is synchronized (signature verification is time-sensitive)

### Issue: "Event not reaching the server"

**Solution**:
1. Check ngrok is running: `curl https://your-ngrok-url.ngrok.io/webhooks/slack/health`
2. Verify Slack app URLs are updated with the ngrok URL
3. Check Slack app has the correct scopes and event subscriptions
4. Look at Slack app's "Event Subscriptions" page for delivery errors

### Issue: "Bot not responding in Slack"

**Solution**:
1. Check server logs for errors
2. Verify the bot is added to the channel
3. Ensure `SLACK_BOT_TOKEN` has the correct scopes
4. Check the `/stats` endpoint to see if events are being processed

### Issue: "URL verification failed"

**Solution**:
1. This happens when Slack first verifies your endpoint
2. The server should automatically respond with the challenge
3. Check server logs for the verification request
4. Ensure the endpoint is accessible from the internet (ngrok running)

## Monitoring

### View Real-time Logs

The test server provides detailed logging:
```
INFO: Received Slack event: app_mention
INFO: Event queued: event_id=abc123
INFO: Processing event: abc123
INFO: Slack processor handling message event
INFO: Sending response to channel C123456
```

### Check Event Queue Statistics

```bash
curl http://localhost:8001/stats
```

### Check Session Activity

The statistics endpoint shows active sessions and their activity.

## Next Steps

Once basic testing is complete:

1. **Connect to CUGA Agent**: Modify `SlackEventProcessor.process_event()` to call the actual CUGA agent
2. **Add Error Handling**: Implement retry logic and error notifications
3. **Add Tests**: Create unit and integration tests
4. **Deploy**: Set up a permanent webhook URL (not ngrok) for production

## Security Notes

- Never commit `.env.slack` to version control
- Rotate tokens regularly
- Use HTTPS in production (ngrok provides this for testing)
- Verify all webhook signatures
- Implement rate limiting for production

## Additional Resources

- [Slack Events API](https://api.slack.com/events-api)
- [Slack Slash Commands](https://api.slack.com/interactivity/slash-commands)
- [Slack Interactive Components](https://api.slack.com/interactivity/components)
- [ngrok Documentation](https://ngrok.com/docs)