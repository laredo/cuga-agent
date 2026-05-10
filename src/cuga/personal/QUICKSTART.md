# CUGA Personal — Quick Start

A walkthrough of the base demo scenario: a PM named Maya uses CUGA via Slack to store product updates, query them, and receive a weekly bulletin for approval.

---

## Prerequisites

- Python 3.12, `uv` installed
- A Slack workspace where you have admin access
- An LLM provider key (OpenAI, WatsonX, etc.)

---

## 1. Install

```bash
uv venv --python=3.12 && source .venv/bin/activate
uv sync
```

---

## 2. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Under **OAuth & Permissions → Scopes → Bot Token Scopes**, add:
   - `chat:write`, `channels:history`, `im:history`, `app_mentions:read`, `users:read`
3. Under **Event Subscriptions**, enable and subscribe to bot events:
   - `message.channels`, `message.im`, `app_mention`
4. Under **Socket Mode**, enable Socket Mode and generate an **App-Level Token** (`connections:write` scope) — this is your `SLACK_APP_TOKEN`
5. Install the app to your workspace → copy the **Bot User OAuth Token** — this is your `SLACK_BOT_TOKEN`
6. Invite the bot to a channel: `/invite @your-bot-name`

---

## 3. Configure environment

Create a `.env` file in the repo root:

```bash
# LLM — pick your provider
OPENAI_API_KEY=sk-...
# or for WatsonX: WATSONX_URL, WATSONX_APIKEY, WATSONX_PROJECT_ID

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# Web search (required for product-scout skill)
TAVILY_API_KEY=tvly-...   # free tier at app.tavily.com

# Optional: point at a non-default backend
# CUGA_BACKEND_URL=http://localhost:7860
```

Then load it:

```bash
source .env
```

---

## 4. Seed the knowledge base (optional but recommended for demo)

This pre-loads three product update entries so the bulletin has content to draw from:

```bash
uv run python scripts/seed_demo_knowledge.py
```

> The script requires the backend to be running. If it isn't, run `cuga personal start` first (it auto-starts the backend), seed in a second terminal, then proceed.

---

## 5. Start the personal agent

```bash
source .env && cuga personal start
```

This will:
- Auto-start the CUGA backend (registry + knowledge store) if not already running
- Load skills from `./skills/`
- Connect to Slack via Socket Mode

You should see:
```
Backend ready — registry:8001, demo:7860
Loaded 1 skill(s): ['bulletin']
Starting CUGA Personal in Slack (Socket Mode)…
```

---

## 6. Run the demo scenario

All interactions are via **@mention** in a Slack channel where the bot is invited.

### Store a product update from a URL
```
@cuga store this for me: https://example.com/release-notes-v3
```

### Store a plain-text note
```
@cuga remember this: We shipped dark mode support in the mobile app this week
```

### Query what's been stored
```
@cuga what did we ship recently?
```

### Schedule the weekly bulletin
```
@cuga every Friday at 4pm, draft a customer bulletin from what we shipped and send it to me for review
```

CUGA will confirm the schedule with the next run time.

### Trigger the bulletin immediately (for demo/testing)

Because Slack intercepts `/` as slash commands, use a text trigger instead:

> Note: schedule the bulletin first, then trigger it with a text message that includes "run bulletin now" or similar — or just wait for the scheduled time.

### Approve and post the bulletin

After the bulletin draft arrives, reply:
```
@cuga approve
```
or to discard:
```
@cuga no
```

---

## 7. Channel Digest

The channel-digest skill summarizes Slack channel history day by day and stores each digest in the knowledge base — making channel conversations searchable by the agent.

**Required Slack scopes** (add these in api.slack.com/apps → OAuth & Permissions if you haven't already):
- `channels:history`, `groups:history`, `im:history`, `mpim:history`

After adding scopes, reinstall the app to the workspace.

### One-shot: summarize a channel on demand

In any channel where the bot is invited:
```
@cuga summarize this channel from the past month and store in knowledge
@cuga digest the last 7 days
@cuga summarize this channel from the past week
```

Supported time periods: `past month` (30 days), `last week` / `past week` (7 days), `today` (1 day), `last N days`.

The agent will report how many days were processed and stored. Digests are immediately queryable:
```
@cuga what was discussed in this channel last week?
```

### Scheduled: daily auto-digest

```
@cuga set a daily job to summarize this channel at 6pm
@cuga every weekday at 5pm digest this channel
```

CUGA confirms the schedule and next run time. Each daily run summarizes the previous day's messages (`lookback_days=1`).

To trigger the scheduled job immediately for testing:
```
/run channel-digest
```

### What gets stored

Each digest is stored as a knowledge entry titled `channel-digest-<channel>-<YYYY-MM-DD>`. The agent can search across all stored digests when you ask questions like "what did the team decide about X last week?"

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `SLACK_BOT_TOKEN is not set` | Run `source .env` before starting |
| `Knowledge engine already running in another process` | Normal warning — the personal agent uses HTTP tools, not a local engine. Safe to ignore. |
| Bot doesn't respond to DMs | Use @mention in a channel instead; App Home DMs may be disabled by workspace policy |
| `ingest_knowledge_url isn't available` | Restart after `source .env`; the backend must be running before the agent starts |
| Seed script returns 400 | Check that the backend is running on port 7860 (`curl http://localhost:7860/health`) |
