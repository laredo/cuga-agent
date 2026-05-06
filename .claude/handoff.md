# CUGA Personal — Claude Handoff

This is the primary working repo as of 2026-05-06. Read this first.

---

## Active repo

**Path:** `/Users/royabitbol/Development/repos/RPA/hackathon/cuga-agent`
**Branch:** `hackathon`
**Push remote:** `origin` → `https://github.com/roy651/cuga-agent.git`

Other repos for reference only:
- `/Users/royabitbol/Development/repos/rpa/cuga-agent-wip-my-claw` — original uncommitted CUGA Personal work
- `/Users/royabitbol/Development/repos/RPA/cuga-agent` — canonical CUGA upstream

---

## What is CUGA Personal?

A personal enterprise automation assistant built as a composition layer on top of CUGA. It automates knowledge-worker chores (timesheets, expenses, HR workflows) via the channels users already use (Slack, CLI).

See `docs/LAYERS.md` for the full four-layer architecture. See `docs/personal/README.md` for user-facing docs.

---

## Four-layer architecture (summary)

| Layer | Source | Key addition |
|---|---|---|
| L1: CUGA base | cuga-project/cuga-agent | LLM orchestration, PolicyEngine, MCP, Secrets |
| L2: Skills support | cuga-project feat/skills-support | Skill discovery, SKILL.md format |
| L3: cuga-claw | laredo/cuga-agent | Typed Event model, SessionRouter, production Slack, ApprovalManager |
| L4: CUGA Personal | Our work | Skill activation, SkillDispatcher, SchedulerEngine, CLIAdapter, CLI |

---

## Implementation status (2026-05-06)

**Complete:**
- 84/84 tests passing in `tests/personal/`
- All four layers merged and committed on `hackathon` branch
- `cuga personal start/doctor/skill/schedule` CLI commands wired
- `docs/LAYERS.md` — layer architecture documentation
- `docs/personal/enterprise-testing-guide.md` — manual testing guide

**Key bug fixed:** `SkillLoader.activate()` was silently a no-op — policy methods were called without `await`. Fixed in `src/cuga/personal/skills/loader.py` with async `_add_policy()`.

**Deferred:**
- Adapt `PersonalAgentOrchestrator` to use laredo's `Event`/`SessionRouter` instead of our `MessageEvent`/`SessionManager` — the two coexist but aren't yet wired together
- SF timesheet integration — parked (requires IT OAuth app registration)
- Scheduler persistence (in-memory only)
- Email adapter (stub at `gateway/adapters/email.py`)

---

## Next phase

User wants to **add a new agent to CUGA** in the hackathon branch, then showcase all four layers together. The showcase candidates are in `docs/LAYERS.md` under "Showcasing Capabilities".

---

## How to run

```bash
cd /Users/royabitbol/Development/repos/RPA/hackathon/cuga-agent
source .venv/bin/activate          # or: uv sync --extra personal
cuga personal doctor               # verify setup
cuga personal start                # interactive CLI session
```

## How to run tests

```bash
uv run pytest tests/personal/ -q   # 84 tests
uv run pytest tests/unit/ -q       # upstream unit tests
uv run ruff check src/cuga/personal/
```

## Key files to read before making changes

- `docs/LAYERS.md` — four-layer architecture overview
- `src/cuga/personal/core/orchestrator.py` — message handling flow
- `src/cuga/personal/skills/loader.py` — skill activation (async policy injection)
- `src/cuga/backend/events/` — laredo's event system (L3)
- `src/cuga/backend/integrations/slack/` — laredo's Slack integration (L3)
- `src/cuga/backend/skills/` — upstream skill discovery (L2)
- `src/cuga/settings.toml` — `[personal]` section at the bottom

## Contribution rules

- Branch: `feature/personal-*` or `fix/personal-*` off `hackathon`
- Commits: Conventional Commits style (no DCO needed on fork)
- Tests: required for all new code
- Linting: `uv run ruff check --fix && uv run ruff format` before commit
- Push to `origin` (roy651 fork), open PR to `upstream` (laredo) when ready
