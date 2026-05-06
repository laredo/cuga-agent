---
name: product-scout
description: "Search the web for recent product updates and store relevant findings in the knowledge base, ready for the weekly bulletin"
version: "0.1.0"
author: "cuga-personal"
platforms: [slack, cli]
requires_tools: [web_search, search_knowledge, ingest_knowledge_text]
commands: ["/scout"]
triggers:
  - type: keyword
    value: ["scout for updates", "search for updates", "find product news", "web scout", "scout the web", "look up updates"]
    operator: or
  - type: natural_language
    value: ["search the web for product updates", "find recent news about", "look for what's new with", "scout for recent information about"]
schedule_hint: "0 15 * * 4"
enterprise:
  category: research
  approval_required: false
  data_classification: internal
---

# Product Scout Skill

Searches the web for recent product updates and stores relevant findings in the knowledge base.
Designed to run on Thursdays at 3pm — one day before the Friday bulletin — so fresh content is ready.

## What this skill does

- Asks the user which product or topic to scout (if not specified)
- Runs 2–3 targeted web searches via Tavily
- Filters results: LLM judges each one for direct relevance to the product
- Deduplicates against existing knowledge base entries
- Stores at most 3 new, relevant items per run
- Reports a summary of what was added

## Usage

On demand:
> "Scout for updates about CUGA agent"
> "Search the web for recent LangGraph releases"
> "/scout"  ← will ask which product to search for

Scheduled (auto-runs Thursday 3pm):
> "Every Thursday at 3pm, scout for product updates about CUGA and store them"

## Scheduling with the bulletin

Pair with the bulletin skill for a fully automated pipeline:
1. Thursday 3pm — product-scout fetches and stores fresh web content
2. Friday 4pm — bulletin drafts from the enriched knowledge base
