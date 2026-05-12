# CUGA Personal — Handoff

**Repo:** `/Users/royabitbol/Development/repos/RPA/hackathon/jims-cuga-fork`
**Branch:** `cuga-claw`

---

## What this project is

A personal productivity layer on top of Jim's fork of the CUGA enterprise agent platform (LangGraph-based). The persona is Maya, a PM who interacts with the agent via Slack.

CUGA's primary SDK classes are `CugaAgent` and `CugaSupervisor` (defined in `src/cuga/sdk.py`). Skills are declarative config bundles (`SKILL.md` + policy files) that configure agent behavior — they are not agents themselves.

---

## Two independent layers — understand both

### Layer A: cuga-personal (Maya's productivity assistant)

**`src/cuga/personal/`** — the personal layer:
- `core/orchestrator.py` — main message handling loop (scheduling → approval gate → normal dispatch)
- `gateway/` — Slack Socket Mode adapter + session manager
- `scheduler/` — cron-based asyncio job runner (`engine.py`) + NL parser (`nl_parser.py`)
- `tools/channel_history.py` — Slack channel fetch + day chunking + LLM summarization + KB storage
- `tools/knowledge.py`, `tools/web_search.py` — KB and Tavily web search tools

**`skills/`** — three working skills:
- `bulletin/` — weekly product update draft with human approval gate
- `product-scout/` — web search via Tavily, stores findings in KB
- `channel-digest/` — summarizes Slack channel history by day, stores digests in KB

**How to run:**
```bash
source .env && cuga personal start
```
Requires: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `OPENAI_API_KEY`, `TAVILY_API_KEY`.
See `src/cuga/personal/QUICKSTART.md` for full setup.

---

### Layer B: Jim's multi-agent swarm (chief-of-staff research)

A fully working research swarm example, separate from the personal layer.

**Framework:** `src/cuga/backend/multi_agent/`
- `config.py` — `MultiAgentConfig` Pydantic model, `load_config()` reads TOML
- `agent_bus.py` — `AgentBus` peer-permission enforcement (ACL)
- `agent_factory.py` — `AgentFactory`, builds agents with MCP tools
- `swarm_factory.py` — `SwarmAgentFactory`, async context manager for swarm pattern; each agent gets its own `EventQueue` inbox; dispatch tools use optional `config` + `**kwargs` to accept injected `thread_id`
- `runner.py` — `ConfigurationRunner`, dispatches to the right pattern runner
- `patterns/` — `pipeline.py`, `peer_to_peer.py`, `supervisor.py`, `swarm.py`

**Patterns supported:** pipeline, peer_to_peer, supervisor, **swarm** (newest)

**The swarm pattern** — async, event-queue-driven:
- Agents run as concurrent `asyncio.Task`s with their own `EventQueue` inbox
- Inter-agent dispatch uses real LangChain tool calls: `dispatch_to_<peer_id>(content="...")`
- Results posted to Slack via `NOTIFY_SLACK:` directives parsed from agent output
- `SwarmBus` ACL: each agent only gets dispatch tools for agents in its own `peers` list
- `task_id` is injected into the seed event and propagated through every peer dispatch so all agents post to the **same** Slack thread
- `cuga_lite_graph.py` auto-wraps `dispatch_to_*` tools at runtime to inject `thread_id`, so worker agents inherit the correct Slack context without needing explicit plumbing in topology config

**Working example:** `docs/examples/chief_of_staff_research/`

Four agents:
- `chief_of_staff` (entry) — receives Slack message, dispatches to `web_searcher` or `summarizer` via tool call; its plain-text output is the immediate Slack ack
- `web_searcher` (worker) — runs 3 web searches, dispatches each result to `fact_checker`; MCP: `cuga-web`
- `fact_checker` (worker) — validates and scores 1–5, discards <3, stores vetted docs to KB with `fact_checker::` prefix; MCP: `cuga-web` + `cuga-knowledge`
- `summarizer` (worker) — reads only `fact_checker::` KB entries, writes score-weighted report to Slack; MCP: `cuga-knowledge` (built-in via `enable_knowledge = true`)

KB namespace convention:
- `web_searcher::<title>` — raw, unvetted
- `fact_checker::<title>` — validated, score ≥ 3

Two Slack workflows:
```
@bot research <topic>      → web_searcher → fact_checker (async, per-source)
@bot summarize <aspect>    → summarizer reads KB, posts report
```

Dashboard + observability:
- FastAPI dashboard on port 7860: agent cards, declared edges, live SSE log stream
- Langfuse tracing (optional, via `LANGFUSE_*` env vars)
- Rotating log at `logs/swarm.log`

**How to run:**
```bash
cd docs/examples/chief_of_staff_research
cp .env.example .env  # fill in OPENAI_API_KEY, SLACK_*, CUGA_SLACK_SOCKET_MODE=true
python run.py
# Dashboard: http://localhost:7860
```

---

## What's been fixed / hardened since initial build

- **Dispatch tool robustness** — `_dispatch_fn` in `swarm_factory.py` accepts optional `config` and `**kwargs` so the LangGraph executor can inject config without crashing.
- **Slack thread propagation** — `task_id` is seeded into the initial `run_swarm` Event payload; `cuga_lite_graph.py` wraps `dispatch_to_*` tools to inject `thread_id` at runtime, ensuring every background worker posts to the correct Slack thread.
- **Security validator** — `security.py` dunder regex tightened from `__` (matched any double-underscore, including filenames like `fact_checker__title`) to `\.__` + standalone dunder names only.
- **Knowledge tool signature** — `client.py` knowledge tool inner functions accept `**kwargs` so `thread_id` injection does not crash.

## Open questions / what's NOT done yet

- **Multi-agent showcase** — both swarms are live and working end-to-end. See `docs/multi_agent_showcase.md` for the demo arc and example prompts. Scenario C (`sanity-check`) is deployed.
- **Scheduler persistence** — jobs are in-memory only, lost on restart. Deferred.
- **Job management via Slack** — no list/delete/pause commands exposed to users yet.

---

## Key files to read before making changes

| File | Why |
|---|---|
| `src/cuga/personal/QUICKSTART.md` | Full setup, all skill usage, troubleshooting |
| `src/cuga/personal/core/orchestrator.py` | Personal layer message flow |
| `src/cuga/personal/gateway/session.py` | Agent creation and tool wiring |
| `src/cuga/personal/scheduler/engine.py` | Job execution, approval gate logic |
| `docs/examples/chief_of_staff_research/topology.toml` | Full swarm topology with inline docs |
| `skills/swarms/chief-of-staff-research/topology.toml` | Live personal-layer version of the research swarm |
| `skills/swarms/sanity-check/topology.toml` | Live sanity check swarm (Option C from scenarios) |
| `src/cuga/personal/core/swarm_router.py` | `SwarmRouter` — discovers swarms from `skills/swarms/`, matches triggers, fires `run_swarm` as `asyncio.Task` |
| `src/cuga/backend/multi_agent/config.py` | TOML schema, `load_config()` |
| `src/cuga/backend/multi_agent/swarm_factory.py` | `SwarmAgentFactory` — entry point for swarm |
| `src/cuga/backend/multi_agent/runner.py` | `ConfigurationRunner` |
| `src/cuga/backend/cuga_graph/nodes/cuga_lite/executors/common/security.py` | Sandbox security validator — dunder/import patterns |
| `src/cuga/backend/knowledge/client.py` | Knowledge tool definitions — must accept `**kwargs` for `thread_id` injection |
| `.claude/ideas/multi-agent-scenarios.md` | Brainstormed options — Option C is now deployed as `sanity-check` |
