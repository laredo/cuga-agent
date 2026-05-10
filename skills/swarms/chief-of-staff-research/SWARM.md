---
name: chief-of-staff-research
description: "Research swarm: searches the web, fact-checks each source, stores vetted findings in the KB. A separate trigger reads the KB and writes a report."
topology: topology.toml
triggers:
  - type: keyword
    operator: or
    value: ["research", "look into", "find info on", "investigate"]
  - type: keyword
    operator: or
    value: ["summarize what we know", "write up", "write a report on"]
---

# Chief of Staff Research Swarm

Builds institutional knowledge over time.

**Research mode** (`research <topic>`):
- `chief_of_staff` acks and dispatches to `web_searcher`
- `web_searcher` runs 3 searches, dispatches each result mid-run to `fact_checker`
- `fact_checker` scores 1–5, discards <3, stores vetted docs as `fact_checker::<title>`

**Summary mode** (`summarize <aspect>`):
- `chief_of_staff` dispatches to `summarizer`
- `summarizer` reads only `fact_checker::` KB entries, posts a structured report

KB prefixes written: `web_searcher::` (raw), `fact_checker::` (vetted)
