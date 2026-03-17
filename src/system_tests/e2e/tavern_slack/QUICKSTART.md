# Slack Integration Tests — Quick Start

This directory contains Tavern-based end-to-end tests for the CUGA Slack bot integration.

## Architecture

Tests use a two-process setup:
1. **CUGA Agent** — the bot under test, running in Socket Mode
2. **Test API Server** — a Flask server (`test_api_server.py`) that wraps the Slack SDK driver and exposes HTTP endpoints for Tavern

```
Tavern YAML → HTTP → Test API Server (port 5555) → Slack SDK → Slack API → CUGA bot → Slack API
```

## Prerequisites

- Python 3.11+
- `uv` package manager
- A Slack workspace with a bot installed (Socket Mode enabled)
- CUGA running with Slack integration configured

## Setup

### 1. Slack App Configuration

Create a Slack app with:
- **Socket Mode** enabled
- **App-Level Token** with `connections:write` scope
- **Bot Token Scopes**: `chat:write`, `channels:history`, `groups:history`, `im:history`
- Bot installed to the channels used for testing

### 2. Environment Variables

Create a `.env` file in this directory:

```bash
# Slack credentials
SLACK_BOT_TOKEN=<your-bot-token>
SLACK_APP_TOKEN=<your-app-token>

# Test configuration
SLACK_TEST_CHANNEL=<your-channel-id>
SLACK_BOT_MENTION=<@your-bot-user-id>
```

Channel IDs look like `C0XXXXXXXXX` and can be found by right-clicking a channel in Slack → "Copy link".

Bot User ID looks like `U0XXXXXXXXX` — find it in your Slack app settings under "App Home".

### 3. Install Dependencies

```bash
cd src/system_tests/e2e/tavern_slack
uv pip install -r requirements.txt
```

## Running Tests

### Step 1: Start CUGA

From the repo root:

```bash
uv run cuga start demo
```

Ensure the Slack integration is configured in your demo config. CUGA must be running and connected via Socket Mode before tests start.

### Step 2: Start the Test API Server

```bash
cd src/system_tests/e2e/tavern_slack
uv run python test_api_server.py
```

The server starts on `http://localhost:5555`. Verify with:

```bash
curl http://localhost:5555/health
```

### Step 3: Run the Tests

```bash
cd src/system_tests/e2e/tavern_slack
uv run pytest specs/ -v
```

Or use the convenience script:

```bash
./run_tests.sh
```

### Run specific test marks

```bash
# Only basic interaction tests
uv run pytest specs/ -v -m "slack and not multi_channel"

# Only multi-channel tests
uv run pytest specs/ -v -m "multi_channel"

# Only thread context tests
uv run pytest specs/ -v -m "thread_context"
```

## Test Structure

| File | Description |
|------|-------------|
| `specs/test_basic_interaction_http.tavern.yaml` | Basic bot responses, thread context, calculations |
| `specs/test_multi_channel_http.tavern.yaml` | Cross-channel isolation and context tests |
| `specs/test_thread_context_http.tavern.yaml` | Thread-level context persistence |
| `specs/test_concurrency_http.tavern.yaml` | Sequential rapid messages and multi-channel sequencing |

## HTTP API Endpoints

The test API server exposes:

- `GET /health` — health check
- `POST /slack/send` — send a message, returns `{ts, channel}`
- `POST /slack/wait` — wait for bot reply in thread, returns message object
- `POST /slack/send_and_wait` — send and wait atomically, returns `{sent: {ts, channel}, response: {text, user, ts}}`
- `GET /slack/get_thread?channel=C...&thread_ts=...` — get all messages in a thread

### send_and_wait payload

```json
{
  "channel": "C0XXXXXXXXX",
  "text": "<@UXXXXXXXXX> hello",
  "thread_ts": "1234567890.123456",  // optional, continues existing thread
  "timeout": 30
}
```

## Troubleshooting

**Tests timeout (408)**
- Ensure CUGA is running and connected to Slack
- Ensure the bot is invited to the test channel(s)
- Check that `SLACK_BOT_MENTION` uses the correct bot user ID (format: `<@UXXXXXXXXX>`)

**`ModuleNotFoundError`**
- Run `uv pip install -r requirements.txt` from within the `tavern_slack` directory

**Context tests fail**
- CUGA always replies in-thread. The `thread_ts` in follow-up messages must be the `ts` of the *first user message* (the thread root), not the bot's reply `ts`.
