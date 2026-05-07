# Idea: Competitive Pre-Brief (multi-agent showcase)

## The scenario

Maya, a PM, types in Slack 20 min before a VP product review:
> `@cuga give me a competitor pulse before my 2pm`

Two peer-to-peer agents synthesize external and internal knowledge:

- **`market_sentinel`** (entry) — web search, scans what competitors shipped in the last 2 weeks
- **`product_strategist`** (exit) — reads Maya's knowledge base, cross-references against competitor moves, produces a battle card

The demo hook: `product_strategist` catches that CompetitorX just shipped something that directly overlaps Maya's Q3 roadmap — a finding neither agent could surface alone.

Output: a 10-line Slack battle card with ⚠️ flags and suggested talking points, ready 90 seconds after the request.

## Why peer-to-peer (not pipeline)

The two agents have genuinely complementary, non-overlapping knowledge:
- `market_sentinel` has live web access but no product context
- `product_strategist` has the KB but no web access

They're not refining each other's work — they're synthesizing two different information streams. That's the correct mental model for peer-to-peer vs. pipeline.

## Demo arc

**Act 1** — Maya stores product updates via `@cuga remember this` over the week. Product-scout auto-runs Thursday and enriches the KB.

**Act 2** — Friday morning, Maya fires the competitor pulse. The two-agent system draws on both live web data and everything stored in Act 1 — making Act 1 retroactively valuable in front of the audience.

The bulletin skill can still run Friday afternoon as a separate capstone.

## Topology TOML

```toml
[configuration]
name    = "competitive_prebrief"
pattern = "peer_to_peer"

[[agents]]
id     = "market_sentinel"
type   = "cuga_lite"
role   = "entry"
peers  = ["product_strategist"]
instructions = """
You are a competitive intelligence analyst with live web access.
Given a topic or trigger:
1. Identify 2-3 key competitors for the product area mentioned.
2. Search the web for what each shipped in the last 2 weeks (changelogs, blogs, HN).
3. Output structured entries:
   COMPETITOR: <name>
   WHAT: <one sentence>
   ANGLE: <positioning>
   SOURCE: <URL>
   DATE: <approx date>
Do not compare to any internal product — that is not your job.
"""

  [[agents.tools]]
  name   = "web_search"
  module = "cuga.personal.tools.web_search"
  func   = "web_search"

[[agents]]
id     = "product_strategist"
type   = "cuga_lite"
role   = "exit"
peers  = ["market_sentinel"]
instructions = """
You are a product strategist with access to the internal knowledge base.
Given competitive intel from market_sentinel:
1. Search the KB for what your team shipped and what is roadmapped.
2. Assess each competitor finding: ahead / behind / differentiated?
3. Flag overlaps with unreleased roadmap items with ⚠️.
4. Output a concise Slack battle card (max 10 lines):
   - One line per competitor (status + what they shipped + your position)
   - "Watch out" section for ⚠️ items with a suggested talking point
"""

  [[agents.tools]]
  name   = "search_knowledge"
  module = "cuga.personal.tools.knowledge"
  func   = "search_knowledge"

[[edges]]
from = "market_sentinel"
to   = "product_strategist"
mode = "peer_to_peer"
```

## Status
Concept only — not implemented. Return to this after the channel-history summarization feature.
