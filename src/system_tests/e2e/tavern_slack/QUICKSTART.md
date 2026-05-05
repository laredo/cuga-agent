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

Two Slack apps are required: the **CUGA bot** (the system under test) and the **CUGA Test Driver** (sends messages and reactions on behalf of a test user).

#### CUGA Bot — required scopes

| Scope | Purpose |
|---|---|
| `app_mentions:read` | Receive `app_mention` events via Socket Mode |
| `chat:write` | Post messages (responses, approvals, rejections) |
| `channels:history` | Read channel history to fetch context |
| `channels:read` | Resolve channel names and metadata |
| `groups:history` | Read private channel history |
| `groups:read` | Resolve private channel names |
| `im:history` | Read DM history |
| `im:read` | Resolve DM metadata |
| `reactions:read` | Receive `reaction_added` / `reaction_removed` events |
| `reactions:write` | Add emoji reactions as processing indicators (thinking, done, error) |

**App-level token** (Socket Mode):
- `connections:write` — required for the WebSocket connection

#### CUGA Test Driver — required scopes

| Scope | Purpose |
|---|---|
| `chat:write` | Send test messages to channels |
| `channels:history` | Poll channel history to detect bot responses |
| `channels:read` | Resolve channel info |
| `groups:history` | Same as above for private channels |
| `groups:read` | Same as above for private channels |
| `im:history` | Same for DMs |
| `im:read` | Same for DMs |
| `reactions:write` | **Add emoji reactions to simulate user reactions** — required for reaction tests |

After adding any missing scope, go to **OAuth & Permissions → Reinstall to Workspace** to regenerate the token with the updated scope list.

Both apps must be invited to the test channels before running tests.

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

The test API server (`test_api_server.py`, port 5555) exposes:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check — returns `{status, bot_id}` |
| `POST` | `/slack/send` | Send a message, returns `{ts, channel}` |
| `POST` | `/slack/wait` | Wait for bot reply in thread, returns message object |
| `POST` | `/slack/send_and_wait` | Send and wait atomically, returns `{sent, response}` |
| `POST` | `/slack/get_thread` | Get all messages in a thread |
| `POST` | `/slack/react` | Add an emoji reaction to a message |
| `POST` | `/slack/react_and_wait` | Add a reaction and wait for bot to respond in that thread |

### Payloads

**send / send_and_wait**
```json
{
  "channel": "C0XXXXXXXXX",
  "text": "<@UXXXXXXXXX> hello",
  "thread_ts": "1234567890.123456",
  "timeout": 30
}
```

**react**
```json
{
  "channel": "C0XXXXXXXXX",
  "timestamp": "1234567890.123456",
  "reaction": "+1"
}
```

**react_and_wait** — adds reaction then polls the thread for a bot reply
```json
{
  "channel": "C0XXXXXXXXX",
  "message_ts": "1234567890.123456",
  "reaction": "+1",
  "timeout": 30
}
```
Returns `{reaction: {...}, response: {text, user, ts}}` on success, or `408` if the bot doesn't reply within `timeout` seconds.

## Test Marks

| Mark | Tests |
|---|---|
| `slack` | All Slack integration tests |
| `reactions` | Reaction-handling tests (`test_reaction_handling_http.tavern.yaml`) |
| `multi_channel` | Cross-channel isolation tests |
| `thread_context` | Thread context persistence tests |

Run a specific group:
```bash
uv run pytest specs/ -v -m "reactions"
uv run pytest specs/ -v -m "slack and not reactions"
```

## Troubleshooting

**Reaction tests fail with `missing_scope: reactions:write`**
- The test driver bot token lacks `reactions:write`.
- Add `reactions:write` to the test driver app at [api.slack.com/apps](https://api.slack.com/apps) → **OAuth & Permissions → Bot Token Scopes**, then click **Reinstall to Workspace** and update `TEST_DRIVER_SLACK_BOT_TOKEN` in `.env` with the new token.

**Tests timeout (408)**
- Ensure CUGA is running and connected to Slack
- Ensure both bots are invited to the test channel(s)
- Check that `CUGA_BOT_USER_ID` is set correctly (format: `U0XXXXXXXXX`)

**`ModuleNotFoundError`**
- Run `uv pip install -r requirements.txt` from within the `tavern_slack` directory

**`InvalidExtFunctionError: Error importing module utils.tavern_helpers`**
- Ensure you are running `pytest` from the repo root (not from inside `tavern_slack/`). The `conftest.py` adds `tavern_slack/` to `sys.path` automatically.

**Context tests fail**
- CUGA always replies in-thread. The `thread_ts` in follow-up messages must be the `ts` of the *first user message* (the thread root), not the bot's reply `ts`.
