# Multi-Agent Showcase in CUGA Personal

> This document explains the multi-agent architecture within the `cuga personal` layer:
> how two swarms coexist, how messages are routed to them, and how this fits into
> the broader personal-layer design.

---

## The two swarms, side by side

| | **Jim's Research Swarm** | **Sanity Check Swarm** |
|---|---|---|
| **Location** | `skills/swarms/chief-of-staff-research/` | `skills/swarms/sanity-check/` |
| **What it does** | Builds knowledge over time. Receives a topic, searches the web, fact-checks each source, stores vetted documents in the KB. A separate trigger reads that KB and writes a report. | Challenges a decision before it's made. Receives a proposal, audits institutional memory (the KB Jim's swarm built), and benchmarks the market simultaneously. |
| **Mental model** | *"Do the research and remember it."* | *"Should I actually do this?"* |
| **Agents** | chief_of_staff → web_searcher → fact_checker; separately: summarizer | dispatcher → internal_auditor ‖ external_benchmarker (concurrent) |
| **Trigger phrases** | `research <topic>`, `summarize <aspect>` | `sanity check`, `reality check`, `review this`, `what do we know about`, `have we tried` |
| **Fan-out** | Per-document (one fact_checker task per source, spawned mid-run as web_searcher finds results) | Per-question (internal_auditor and external_benchmarker dispatched simultaneously by the dispatcher) |
| **KB role** | **Writer** — stores raw (`web_searcher::`) and vetted (`fact_checker::`) documents | **Reader** — internal_auditor searches `fact_checker::` entries; also reads personal-layer KB built by product-scout / channel-digest |
| **Async Slack output** | `NOTIFY_SLACK:` lines from fact_checker (one per vetted source) + final summary from summarizer | `NOTIFY_SLACK:` blocks from both workers — internal audit findings + market benchmark — posted independently as they complete |

The two swarms are **complementary by design**: Jim's swarm builds the institutional knowledge base; the sanity check swarm uses it. This is the demo arc: *Act 1* (research runs over days/weeks) → *Act 2* (sanity check draws on that accumulated KB).

---

## Will both swarms run inside `cuga personal start`?

**Yes.** The `SwarmRouter` supports multiple topologies through config-driven discovery. It automatically scans the `skills/swarms/` directory at startup.

Each swarm is its own subdirectory containing:
1. `topology.toml` — The swarm definition
2. `SWARM.md` — The metadata and trigger configuration

To add a new swarm, you simply drop a new folder with these two files into `skills/swarms/`. The router reads the `triggers` from the `SWARM.md` frontmatter.

Example `SWARM.md` configuration for the research swarm:
```yaml
---
name: chief-of-staff-research
topology: topology.toml
triggers:
  - type: keyword
    operator: or
    value: ["research", "look into", "find info on", "investigate"]
  - type: keyword
    operator: or
    value: ["summarize what we know", "write up", "write a report on"]
---
```

Because the trigger sets for the two swarms don't overlap, the router correctly dispatches incoming messages to the right swarm.

---

## How message routing works — the full picture

`cuga personal start` runs a single Slack socket. Every incoming message passes through the orchestrator's **sequential gate chain**:

```
Incoming Slack message
        │
        ▼
┌───────────────────────────────────────────────────┐
│  Step 0 · SwarmRouter  (NEW)                      │
│  "Does this look like a multi-agent trigger?"     │
│  Patterns: regex match on swarm trigger phrases   │
│  → YES: fire ConfigurationRunner as asyncio.Task  │
│          return ack immediately, workers run async │
│  → NO: fall through                               │
└───────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────┐
│  Step 1 · Scheduler                               │
│  "Does this look like a scheduling request?"      │
│  "Every Friday at 4pm, run the bulletin"          │
│  → YES: create ScheduledJob, confirm              │
│  → NO: fall through                               │
└───────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────┐
│  Step 2 · /run <skill>  (immediate job trigger)   │
│  → YES: execute job now                           │
│  → NO: fall through                               │
└───────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────┐
│  Step 3 · Approval gate                           │
│  "Is there a pending draft awaiting approval?"    │
│  Words: approve / yes / discard / no / cancel...  │
│  → YES: post or discard pending artifact          │
│  → NO: fall through                               │
└───────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────┐
│  Step 4 · SkillDispatcher  (the "prior router")   │
│  Two-phase: slash command → keyword trigger       │
│  Activates one of: bulletin / product-scout /     │
│  channel-digest (or NL match in future)           │
│  → MATCH: activate skill on CugaAgent, invoke    │
│  → NO MATCH: invoke CugaAgent with no skill      │
└───────────────────────────────────────────────────┘
        │
        ▼
     CugaAgent.invoke()
     (single-agent, synchronous reply)
```

### What is the "prior router"?

The `SkillDispatcher` (Step 4) is the existing router for single-agent skills. It matches:
- **Slash commands** — `/bulletin`, `/scout` (exact match, fast)
- **Keyword triggers** — defined in each skill's `SKILL.md` frontmatter (e.g. `product update`, `competitor`, `digest`)

It is a *configuration-driven* router: each skill declares what triggers it, and the dispatcher checks them in order.

The new `SwarmRouter` (Step 0) is a *code-driven* router for multi-agent workflows. It runs before the skill dispatcher because swarm triggers need to be intercepted before the single-agent path activates — if "sanity check" fell through to the SkillDispatcher and then to CugaAgent, you'd get a single-agent response, not a swarm.

### Why Step 0?

```
SwarmRouter comes first because:

  "sanity check this" → if it reached SkillDispatcher
                          → no skill keyword matches
                          → CugaAgent answers alone (wrong)

  "sanity check this" → SwarmRouter intercepts
                          → fires dispatcher + two workers concurrently
                          → ack posted, workers post async (correct)
```

---

## Does it make sense to add routing layers to CUGA's orchestrator?

**The honest answer: yes, but the right long-term shape is different from what we've built.**

What we've done is pragmatic and correct for a hackathon — we added Step 0 as a hardcoded gate before Step 4. It works. But it's worth understanding the architectural pressure this creates and what the right abstraction is.

### Current shape (layered if/else)

```
Orchestrator.handle_message()
  if swarm_router.try_handle():  return   # Step 0 — us
  if scheduler.try_handle():     return   # Step 1 — existing
  if run_now.try_handle():       return   # Step 2 — existing
  if approval_gate.try_handle(): return   # Step 3 — existing
  skill_dispatcher.dispatch()             # Step 4 — existing
  agent.invoke()
```

Each step is a separate concern, ordered by specificity (most specific first). This is a **chain-of-responsibility** pattern and it's structurally sound. The issue is that it's implicit — new capabilities require editing the orchestrator.

### The right long-term shape

A `MessageRouter` that owns the chain explicitly:

```python
class MessageRouter:
    """Ordered chain of handlers. First match wins."""
    
    def register(self, handler: MessageHandler, priority: int) -> None: ...
    async def route(self, event, target) -> bool: ...
```

Each handler (`SwarmHandler`, `SkillHandler`, `SchedulerHandler`, `ApprovalHandler`) is a registered plugin. The orchestrator becomes thin:

```python
async def handle_message(self, event, target):
    await self._router.route(event, target)
```

This is the right abstraction if CUGA personal grows beyond a hackathon. For now, the layered if/else is fine — it's readable, it works, and it's easy to reason about.

---

## Execution model comparison

The two swarms use the same underlying `run_swarm()` function but differ in how work fans out:

### Jim's Research Swarm — serial entry, per-document fan-out

```
Slack: "@bot research agentic AI"
        │
        ▼
[chief_of_staff]  ──dispatch_to_web_searcher()──▶  [web_searcher]
     │ (acks Slack immediately)                          │
     │                                           for each result (up to 15):
     │                                           dispatch_to_fact_checker()
     │                                                   │
     │                                           [fact_checker #1]  NOTIFY_SLACK: ✅ source1
     │                                           [fact_checker #2]  NOTIFY_SLACK: ❌ source2
     │                                           [fact_checker #N]  NOTIFY_SLACK: ✅ sourceN
     │
     │   Later: "@bot summarize agentic AI"
     └──dispatch_to_summarizer()──▶  [summarizer]
                                          │ reads fact_checker:: KB entries
                                          └─NOTIFY_SLACK: ## Executive Summary...
```

**Key property:** fact_checker tasks are spawned *mid-run* inside web_searcher's ReAct loop — as each document is found, not after all searches complete. This is true concurrent fan-out.

### Sanity Check Swarm — parallel entry, concurrent workers

```
Slack: "@bot sanity check [proposal text]"
        │
        ▼
[dispatcher]  ──dispatch_to_internal_auditor()──▶  [internal_auditor]
     │         ──dispatch_to_external_benchmarker()──▶  [external_benchmarker]
     │ (acks Slack immediately)
     │
     │                    [internal_auditor]
     │                    searches KB (fact_checker::, channel-digest::, product-scout::)
     │                    └─NOTIFY_SLACK: ## 🏛️ Internal Audit...
     │
     │                    [external_benchmarker]
     │                    3 web searches, collects findings
     │                    └─NOTIFY_SLACK: ## 🌐 Market Benchmark...
     │
     (both workers post independently as they finish — order not guaranteed)
```

**Key property:** both workers receive the *same* full proposal text and run entirely in parallel. Neither waits for the other. The user sees two separate Slack messages posted in whichever order the workers finish.

---

## KB data flow — the full picture

```
Personal layer (skills)                 Jim's research swarm
─────────────────────                   ────────────────────
product-scout skill                     web_searcher
  → web search                            → web search
  → KB: product-scout::<title>            → KB: web_searcher::<title> (raw)
                                               │
channel-digest skill                    fact_checker
  → Slack history                          → validates with web search
  → KB: channel-digest::<date>             → KB: fact_checker::<title> (vetted, score ≥3)
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │   Shared local KB   │
                                    │   (SQLite engine)   │
                                    └─────────────────────┘
                                               │
                                    Sanity Check Swarm
                                    ──────────────────
                                    internal_auditor
                                      → knowledge_search_knowledge()
                                      → reads fact_checker::, channel-digest::,
                                        product-scout:: entries
                                      → surfaces institutional history
```

All four KB namespaces live in the **same SQLite collection** (scoped to the topology name by `AgentFactory._inject_kb_scope`). Agents distinguish provenance by title prefix, not by collection. The sanity check swarm's `internal_auditor` can read everything the personal skills and Jim's research swarm have ever written.

---

## Running both swarms

```bash
# Start the personal orchestrator
source .env && cuga personal start

# What you'll see at startup:
# Loaded 3 skill(s): ['bulletin', 'product-scout', 'channel-digest']
# [SwarmRouter] registered 'chief-of-staff-research' (8 trigger keywords)
# [SwarmRouter] registered 'sanity-check' (8 trigger keywords)
# Swarm router loaded: ['chief-of-staff-research', 'sanity-check']
# Starting CUGA Personal in Slack (Socket Mode)…
```

### Examples: Triggering the Research Swarm
*This swarm **writes** to the Knowledge Base.*
- `@bot research agentic AI frameworks` → Spawns the web searcher and fact checker pipeline. Posts one Slack update per vetted source.
- `@bot summarize what we know about agentic AI frameworks` → Reads all `fact_checker::` KB entries and posts an executive summary with score-weighted key findings.

### Examples: Triggering the Sanity Check Swarm
*This swarm **reads** from the Knowledge Base and checks external sources.*

**Review Mode** — triggers both internal auditor + external benchmarker concurrently:
- `@bot sanity check our proposal to build a custom multi-agent orchestration layer on top of PydanticAI instead of using LangGraph.`
- `@bot sanity check: we should migrate our entire backend to a serverless architecture next quarter.`
- `@bot reality check this before I send it — [paste proposal]`

**Knowledge Mode** — triggers only the internal auditor (KB search):
- `@bot what do we know about agentic frameworks?` → Searches only institutional memory; no web access.

### The "golden path" demo arc

```
Day 1: @bot research agentic AI frameworks
       └─ web_searcher + fact_checker build the KB (10–15 vetted sources)

Day 2: @bot sanity check our proposal to build on PydanticAI instead of LangGraph.
       ├─ internal_auditor searches the KB built in Day 1
       │   └─ "Vetted research from 10-May identifies orchestration latency as key risk"
       └─ external_benchmarker searches the web concurrently
           └─ "Industry trend: most teams standardise on LangGraph for production swarms"
```

This is the moment neither agent could produce alone.
