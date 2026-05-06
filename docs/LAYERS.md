# CUGA Hackathon — Architecture Layers

This document describes the four layers that make up this branch. Each layer builds on the previous one, adding distinct capabilities.

---

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Layer 4: CUGA Personal                            │
│                                                                            │
│   SkillDispatcher    SchedulerEngine    CLIAdapter    Orchestrator         │
│  (slash/keyword/NL)  (croniter jobs)   (stdin/out)   (wires all layers)   │
│                                                                            │
├──────────────────────────────────────────────────────────────────────────┤
│                       Layer 3: laredo/cuga-claw                            │
│                                                                            │
│   Typed Event Model   SessionRouter   Slack Integration   ApprovalGate    │
│   (all sources)       (main/isolated)  (webhook + WS)    (human-in-loop)  │
│                                                                            │
├──────────────────────────────────────────────────────────────────────────┤
│                     Layer 2: feat/skills-support                           │
│                                                                            │
│            Skill Discovery    SKILL.md Format    SkillRegistry             │
│                                                                            │
├──────────────────────────────────────────────────────────────────────────┤
│                       Layer 1: CUGA Agent (base)                           │
│                                                                            │
│    LLM Orchestration   PolicyEngine   ToolRegistry   MCP   Secrets        │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — CUGA Agent (base)

The core CUGA engine: LLM orchestration, a policy system (playbooks, intent guards, tool approvals), MCP tool registry, multi-provider LLM support (WatsonX, OpenAI, Azure), secrets management, and observability. Everything above composes on top of this — none of it is replaced.

---

## Layer 2 — feat/skills-support

Adds skill discovery to the CUGA core. Skills are filesystem bundles — a `SKILL.md` file with YAML frontmatter (`name`, `description`, `requirements`) and a markdown body. The `discover_skills()` function scans standard paths (`~/.config/agents/skills`, `.agents/skills`) and makes skill descriptions available to the LLM as additional context.

This layer answers: *what skills exist and what do they do?*

---

## Layer 3 — laredo/cuga-claw

Transforms CUGA from a request/response tool into an **event-driven system**. Eight commits adding production-grade infrastructure for multi-channel, async agent operation.

### Unified Event Model

All inbound signals — Slack messages, GitHub webhooks, cron ticks, heartbeats — are normalised into a single `Event` envelope with typed `EventType`, `EventSource`, `EventPriority`, and retry counters. Adding a new integration means registering a handler; nothing else changes.

```python
Event(
    type=EventType.SLACK,
    source=EventSource.WEBHOOK,
    event_name="message",
    payload={...},
    priority=EventPriority.NORMAL,
)
```

### SessionRouter — Context vs. Isolation

A critical design insight: not all events should share the same conversation context. The `SessionRouter` routes events to either:

- **Main session** — conversation context is preserved across turns (DMs, @mentions, commands). The agent remembers what was said.
- **Isolated session** — independent execution with no shared context (reactions, background tasks, heartbeats). Prevents cross-contamination.

Routing is set at the adapter layer via `metadata["session_target"]`.

### Production Slack Integration

Two delivery modes, toggled by env var:

| Mode | How | When to use |
|---|---|---|
| Socket Mode | Bolt WebSocket, no public URL | Local dev, corporate firewalls |
| Webhook | FastAPI routes, HMAC-SHA256 + replay protection | Production |

Handles messages, slash commands, and interactive components (button clicks → approval responses).

### Human-in-the-Loop Approval Gate

`ApprovalManager` blocks agent execution with an `asyncio.Event` until a human responds via Slack button. Pattern:

```
Agent wants to call a tool
  → ApprovalRequest created, asyncio.Event set to wait
  → Slack sends interactive message with Approve / Deny buttons
  → User clicks → Slack interaction → event released
  → Agent proceeds or aborts
```

### HeartbeatManager

Runs registered monitoring tasks in batches via `asyncio.gather`, always targeting the main session. Designed to batch multiple health/status checks into a single LLM call — reducing cost vs. separate cron invocations.

---

## Layer 4 — CUGA Personal

Adds the **application layer** that was missing from all three layers below: skill activation, routing, scheduling, and a user-facing CLI. This is what turns CUGA into a personal enterprise automation assistant.

### Skill Activation (vs. Discovery)

Layer 2 discovers skills. Layer 4 **activates** them. When a skill is dispatched, `SkillLoader.activate()` does three things:

1. **Injects policies** — the skill's `policies/*.md` files (playbooks, tool approvals) are loaded into the agent's live policy engine via `await agent.policies.add_playbook(...)`. The agent now behaves according to the skill's rules for this session.
2. **Loads knowledge** — `knowledge/*.md` files are injected as system context (domain data, project codes, rules).
3. **Wires tools** — `mcp_servers.yaml` declares the MCP tool servers the skill needs.

```
User: /timesheet
  → SkillDispatcher matches → mock-timesheet skill
  → activate(): loads timesheet playbook into policy engine
  → agent.invoke(): now follows the 7-step workflow
```

### SkillDispatcher — Three-Tier Routing

Skills are activated by matching the incoming message against three tiers in order:

```
1. Slash command   /timesheet → exact match on skill commands list
2. Keyword trigger "fill my timesheet" → keyword in skill triggers
3. NL/semantic     (Phase 2) → embedding similarity
```

### SchedulerEngine — Cron-Triggered Skills

Skills can run on a schedule without user input. `SchedulerEngine` manages `ScheduledJob` objects with full lifecycle (`ACTIVE`, `PAUSED`, `COMPLETED`, `FAILED`), cron expression parsing via `croniter`, and delivery of results back to any channel.

```python
ScheduledJob(
    skill_name="mock-timesheet",
    schedule="0 16 * * 5",       # Every Friday at 4pm
    prompt="Fill my timesheet for this week",
    delivery=DeliveryTarget(platform="slack", channel_id="C123"),
)
```

### PersonalAgentOrchestrator

The central wiring layer. Every inbound event flows through:

```
MessageEvent
  → SessionManager  (get/create session → thread_id)
  → SkillDispatcher (which skill, if any)
  → SkillLoader.activate() (inject policies + knowledge)
  → CugaAgent.invoke() (execute with full policy engine)
  → ChannelAdapter.send() (deliver response)
```

### CLIAdapter — Reference Implementation

`stdin/stdout` gateway for local development and testing without Slack. Run `cuga personal start` and interact directly. Detects slash commands, maintains session continuity across turns.

### `cuga personal` CLI

Full command surface for managing the personal layer:

```bash
cuga personal start              # Start gateway (CLI or Slack)
cuga personal doctor             # Verify dependencies and config
cuga personal skill list         # Show available skills
cuga personal skill create       # Scaffold a new skill bundle
cuga personal schedule list      # Show scheduled jobs
cuga personal schedule create    # Create a new cron job
cuga personal schedule run <id>  # Trigger a job immediately
```

---

## What Each Layer Adds — Summary

| Capability | L1 Base | L2 Skills | L3 cuga-claw | L4 Personal |
|---|:---:|:---:|:---:|:---:|
| LLM execution | ✓ | ✓ | ✓ | ✓ |
| Policy engine | ✓ | ✓ | ✓ | ✓ |
| Skill discovery | | ✓ | ✓ | ✓ |
| Typed event model | | | ✓ | ✓ |
| Session routing (main/isolated) | | | ✓ | ✓ |
| Production Slack (HMAC, dual mode) | | | ✓ | ✓ |
| Human-in-the-loop approval | | | ✓ | ✓ |
| Skill activation (policy injection) | | | | ✓ |
| Slash/keyword skill dispatch | | | | ✓ |
| Cron scheduler | | | | ✓ |
| CLI gateway | | | | ✓ |
| `cuga personal` CLI commands | | | | ✓ |

---

## Showcasing Capabilities

*Deferred to next phase — a new agent being added may provide a better demo vehicle for all layers together.*

Candidates when ready:

1. **Skill dispatch via CLI** — `cuga personal start`, send `/calc 15% of 1240`, observe policy injection in debug logs
2. **Scheduled job** — `cuga personal schedule run <id>` triggers a skill immediately without waiting for the cron tick
3. **Slack approval flow** — trigger a tool that requires approval, observe the Slack button interaction blocking and resuming the agent
4. **Session isolation** — show that a reaction event doesn't pollute the main conversation thread
5. **Multi-skill session** — switch between `/timesheet` and `/calc` in the same CLI session, observe session continuity
