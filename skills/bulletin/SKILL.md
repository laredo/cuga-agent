---
name: bulletin
description: "Draft a customer-facing product update bulletin from stored knowledge, deliver via Slack for approval before posting"
version: "0.1.0"
author: "cuga-personal"
platforms: [slack, cli]
requires_tools: [knowledge]
commands: ["/bulletin"]
triggers:
  - type: keyword
    value: ["draft bulletin", "compile bulletin", "customer bulletin", "product bulletin", "send the bulletin"]
    operator: or
  - type: natural_language
    value: ["draft a customer update", "compile what we shipped", "create the weekly bulletin", "what should I share with customers"]
schedule_hint: "0 16 * * 5"
enterprise:
  category: communications
  approval_required: true
  data_classification: external
---

# Bulletin Skill

Synthesizes stored knowledge entries into a polished customer-facing product update bulletin.
Designed to run on a schedule (default: Fridays at 4pm) or on demand.

## What this skill does

- Queries the knowledge base for recent product updates, features, and insights
- Synthesizes them into a formatted bulletin suitable for customers or stakeholders
- Presents the draft for human approval before posting to any channel
- On approval, posts to the designated Slack channel (#product-updates by default)

## Bulletin format

The output follows this structure:
- Header: "CUGA Product Update — [Week/Date]"
- 2–4 bullet highlights (one per stored item, customer-framed)
- One closing "What's next" line (brief, forward-looking)

## Scheduling

Set up automatic weekly delivery with:
> "Every Friday at 4pm, draft a customer bulletin from what we've shipped and send it to me for review"
