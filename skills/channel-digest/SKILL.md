---
name: channel-digest
description: "Summarize Slack channel history day by day and store each digest in the knowledge base; supports one-shot and scheduled recurring runs"
version: "0.1.0"
author: "cuga-personal"
platforms: [slack]
requires_tools: [fetch_and_digest_channel]
commands: ["/digest"]
triggers:
  - type: keyword
    value: ["summarize this channel", "digest this channel", "store channel history", "summarize the channel", "channel digest", "digest the channel"]
    operator: or
  - type: natural_language
    value: ["summarize all information in this channel", "store what was said in this channel", "set a daily job to summarize this channel", "digest the last month of messages", "summarize messages from this channel"]
schedule_hint: "0 18 * * *"
enterprise:
  category: knowledge-management
  approval_required: false
  data_classification: internal
---

# Channel Digest Skill

Fetches Slack channel history, summarizes it day by day, and stores each digest in the knowledge base.

## What this skill does

- Fetches all messages in the current channel for the requested period
- Groups by calendar day; splits days with more than 150 messages into sub-chunks
- Summarizes each chunk (OpenAI if available, extractive fallback otherwise)
- Stores each digest tagged with channel name and date — immediately searchable
- Reports how many days were processed

## Usage

One-shot (from Slack):
```
@cuga summarize this channel from the past month and store in knowledge
@cuga digest the last 7 days
/digest
```

Recurring job:
```
@cuga set a daily job to summarize this channel at 6pm
@cuga every weekday at 5pm digest this channel
```

## What gets stored

Each digest is stored as a knowledge entry titled `channel-digest-<channel>-<YYYY-MM-DD>`.
Searchable with queries like "what was discussed in #product-updates last week?"
