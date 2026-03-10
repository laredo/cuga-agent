# Quick Test Guide - Slack Integration

## 🚀 Fastest Way to Test (5 minutes)

### 1. Setup Environment (1 min)
```bash
# Create .env.slack file
cat > .env.slack << EOF
SLACK_BOT_TOKEN=xoxb-your-actual-token-here
SLACK_SIGNING_SECRET=your-actual-secret-here
EOF
```

### 2. Start Test Server (30 sec)
```bash
python src/system_tests/e2e/test_slack_integration.py
```

### 3. Start ngrok (30 sec)
```bash
# In a new terminal
ngrok http 8001
```

Copy the `https://xxxxx.ngrok.io` URL from ngrok output.

### 4. Update Slack App (2 min)
Go to https://api.slack.com/apps → Your App → Update these URLs:

- **Event Subscriptions** → Request URL: `https://xxxxx.ngrok.io/webhooks/slack/events`
- **Slash Commands** → Edit `/cuga` → Request URL: `https://xxxxx.ngrok.io/webhooks/slack/commands`
- **Interactivity** → Request URL: `https://xxxxx.ngrok.io/webhooks/slack/interactions`

### 5. Test! (1 min)

**In Slack:**
```
@cuga hello!
```

**Check server logs** - you should see:
```
INFO: Received Slack event: app_mention
INFO: Processing event...
```

**Check stats:**
```bash
curl http://localhost:8001/stats
```

## ✅ Success Indicators

- ✅ Server starts without errors
- ✅ ngrok shows forwarding URL
- ✅ Slack app URLs save successfully (green checkmark)
- ✅ Mentioning bot in Slack triggers server logs
- ✅ `/stats` shows `processed > 0`

## ❌ Common Issues

| Issue | Solution |
|-------|----------|
| "Slack integration not configured" | Check `.env.slack` file exists and has correct tokens |
| "Signature verification failed" | Verify `SLACK_SIGNING_SECRET` matches Slack app settings |
| "Connection refused" | Ensure test server is running on port 8001 |
| "URL verification failed" | Check ngrok is running and URL is correct |
| Bot doesn't respond | Verify bot is added to the channel |

## 📊 Monitoring Commands

```bash
# Check health
curl http://localhost:8001/webhooks/slack/health

# Check statistics
curl http://localhost:8001/stats

# View logs
# Just watch the terminal where test_slack_integration.py is running
```

## 🎯 What Gets Tested

1. **Event Queue**: Async event processing
2. **Event Processor**: Routes events to Slack processor
3. **Slack Processor**: Handles Slack-specific events
4. **Webhook Routes**: FastAPI endpoints with signature verification
5. **Session Management**: Tracks conversation sessions

## 📝 Test Scenarios

### Scenario 1: App Mention
```
In Slack: @cuga what's the weather?
Expected: Server logs show event processing
```

### Scenario 2: Direct Message
```
In Slack: DM the bot directly
Expected: Server logs show message event
```

### Scenario 3: Slash Command
```
In Slack: /cuga help
Expected: Server logs show command processing
```

### Scenario 4: Button Click
```
In Slack: Click a button in bot's message
Expected: Server logs show interaction event
```

## 🔧 Debug Mode

Add this to see more details:
```python
# In test_slack_integration.py, change log_level
uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
```

## 📚 Full Documentation

- Setup: `SLACK_APP_SETUP_GUIDE.md`
- Testing: `SLACK_TESTING_GUIDE.md`
- Architecture: `webhook-architecture-summary.md`
- Implementation: `webhook-implementation-plan.md`

## 🎉 Next Steps After Testing

1. Integrate with main CUGA server (see `SLACK_TESTING_GUIDE.md` Option 2)
2. Connect to CUGA agent for actual AI responses
3. Add unit tests
4. Deploy to production with permanent webhook URL