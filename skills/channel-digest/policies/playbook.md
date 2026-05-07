---
type: playbook
name: channel-digest-playbook
triggers:
  - type: keyword
    value: ["summarize this channel", "digest this channel", "store channel history", "channel digest"]
    operator: or
priority: 1
---

## Channel Digest Workflow

### 1. Extract parameters from the input

Your input will always begin with `[channel: <ID> name: <name>]` — this is injected automatically.
Extract:
- `channel_id`: the ID portion (e.g. `C12345678`)
- `channel_name`: the name portion (e.g. `product-updates`)
- `lookback_days`: parse from the user's message:
  - "past month" / "last month" → 30
  - "last week" / "past week" → 7
  - "today" → 1
  - "last N days" → N
  - no period specified, or scheduled daily run → 1

### 2. Call `fetch_and_digest_channel`

Pass the extracted `channel_id`, `lookback_days`, and `channel_name`.
This tool handles everything: fetching, chunking, summarizing, and storing.
Do not attempt these steps yourself.

### 3. Report back

Relay the tool's report to the user as-is.
If the tool returns an error, show it clearly:
- `SLACK_BOT_TOKEN not set` → "Add SLACK_BOT_TOKEN to your .env and restart."
- `Slack API error: not_in_channel` → "I need to be invited to that channel first: `/invite @cuga`"
- `OPENAI_API_KEY not set` → Digests were stored using excerpt-only summaries; add OPENAI_API_KEY for full summaries.

## Important constraints

- Never ask the user for the channel_id — it is always injected into the prompt
- Do not try to fetch or paginate messages yourself — the tool handles all of that
- For scheduled daily runs, always use `lookback_days=1`
- Do not create knowledge entries yourself — `fetch_and_digest_channel` handles storage
