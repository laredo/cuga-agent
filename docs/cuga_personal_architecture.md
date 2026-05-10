# CUGA Personal: Architecture & Additions

This document outlines the custom orchestration layer built for `cuga personal` on top of the core CUGA SDK. It explains *why* these custom components were built instead of using native CUGA mechanisms, and how they manifest in the showcase scenarios.

---

## Why build a custom orchestrator?

The core CUGA SDK (`CugaAgent`, `CugaSupervisor`) is an API-first framework designed to be consumed by a FastAPI backend and a React frontend. It handles state management, tool execution, and LLM orchestration excellently. 

However, `cuga personal` is designed to be an asynchronous, Slack-first, scheduled automation assistant. To bridge the gap between CUGA's core capabilities and this use case, we built a custom orchestration layer.

Here is a breakdown of the custom components, why CUGA built-ins weren't sufficient, and how they work in practice.

### 1. The Gateway & Slack Integration
**The Gap:** CUGA does not natively support persistent, two-way Socket Mode connections to chat platforms like Slack.
**The Addition:** We built `SlackAdapter` and the `Gateway` interface. This allows `cuga personal` to maintain a long-lived websocket connection to Slack, parsing threaded conversations, slash commands, and `@mentions` into platform-agnostic `MessageEvent` objects.
**Manifestation:** In the showcase, you can `@bot research agentic AI` directly in Slack, and the resulting tasks will post updates asynchronously into the same Slack thread.

### 2. Rule-Based Routing (`SkillDispatcher` & `SwarmRouter`)
**The Gap:** CUGA has `CugaSupervisor`, which uses an LLM to decide which sub-agent should handle a task. However, routing *every single* incoming Slack message through an LLM just to decide if the user wants to schedule a job, draft a bulletin, or run a sanity check is too slow, expensive, and prone to hallucinations.
**The Addition:** We built deterministic, configuration-driven routers. 
- `SkillDispatcher` parses `SKILL.md` frontmatter for slash commands and keyword regexes.
- `SwarmRouter` parses `SWARM.md` frontmatter for multi-agent trigger phrases.
**Manifestation:** If you type `"sanity check this proposal"`, the `SwarmRouter` instantly and deterministically catches it via a regex match and fires the multi-agent swarm without wasting an LLM call on routing.

### 3. The Scheduler (`SchedulerEngine`)
**The Gap:** CUGA has no native cron engine or background job scheduler.
**The Addition:** We added a `SchedulerEngine` using `croniter` running on a background `asyncio` loop. It parses natural language (e.g., "Every Friday at 4pm...") into cron syntax and automatically invokes agents at the specified times.
**Manifestation:** You can tell the bot: *"Every Friday at 4pm, draft a customer bulletin from what we've shipped"*. The system will wake up, run the `bulletin` skill using a `CugaAgent`, and send you the draft.

### 4. Swarm Concurrency (`ConfigurationRunner`)
**The Gap:** `CugaSupervisor` orchestrates agents *sequentially* (Supervisor → Worker A → Supervisor → Worker B). There is no built-in mechanism for true concurrent fan-out where workers execute simultaneously and report back independently.
**The Addition:** We implemented a custom `run_swarm` pattern via the `ConfigurationRunner`. It parses a `topology.toml` file and spawns `asyncio.Task` instances for each worker, allowing them to run in parallel.
**Manifestation:** In the **Sanity Check Swarm**, the `dispatcher` sends the proposal to the `internal_auditor` (checking the KB) and the `external_benchmarker` (searching the web) *at the exact same time*. Both agents run their ReAct loops concurrently and post `NOTIFY_SLACK:` messages to the user independently as soon as they finish.

---

## The One Exception: The Approval Gate

There is one area in `cuga personal` where a native CUGA mechanism exists but was bypassed in favor of a custom hack: **Human-in-the-Loop (HITL) Approvals.**

Currently, the orchestrator uses a naive text-matching system: if an agent outputs text that "looks like a draft" (e.g., contains "CUGA Product Update"), the orchestrator pauses, stores it in memory, and waits for the user to type "approve" or "yes" before posting it to a channel.

**The Native Alternative:** 
CUGA has native LangGraph HITL built-in. A `CugaAgent` can be configured to yield an interrupt mid-graph. The execution state is frozen, and the agent can be cleanly resumed using `agent.invoke(..., action_response=approval)` once the user provides input. 

While the custom text-matching gate works for the current hackathon demo, migrating the approval flow to use CUGA's native HITL interrupts would be the correct architectural move for a production-ready system.
