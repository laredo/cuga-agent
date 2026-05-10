---
name: sanity-check
description: "Pre-decision review swarm: audits institutional memory (KB) and benchmarks the market simultaneously. Challenges a proposal before it's made."
topology: topology.toml
triggers:
  - type: keyword
    operator: or
    value: ["sanity check", "reality check", "review this", "check this before"]
  - type: keyword
    operator: or
    value: ["what do we know about", "what's in the kb about", "have we tried", "did we try"]
---

# Sanity Check Swarm

Challenges a decision before it's made.

**Review mode** (`sanity check <proposal>`):
- `dispatcher` acks and dispatches to BOTH workers concurrently
- `internal_auditor` searches KB for institutional history — "have we tried this?"
- `external_benchmarker` searches the web — "what has the industry learned?"
- Both post async NOTIFY_SLACK: reports independently as they finish

**Status mode** (`what do we know about <topic>`):
- `dispatcher` dispatches to `internal_auditor` only (KB search, no web)

KB prefixes read: `fact_checker::`, `channel-digest::`, `product-scout::`
