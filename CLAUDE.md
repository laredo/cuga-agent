# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
uv venv --python=3.12 && source .venv/bin/activate
uv sync

# Run the demo
cuga start demo_crm --read-only

# Lint
ruff check src/
ruff format src/

# Run all tests
pytest

# Run a single test file
pytest tests/unit/test_event_models.py -v

# Run tests matching a keyword
pytest -k "test_slack" -v

# Run the tools registry server
uv run python -m cuga.backend.tools_env.registry.registry.api_registry_server

# Install browser support (required for hybrid/browser mode)
playwright install chromium
```

## Configuration

- LLM provider is set via `AGENT_SETTING_CONFIG` env var pointing to a TOML in `src/cuga/configurations/models/` (e.g. `settings.openai.toml`, `settings.watsonx.toml`, etc.)
- Main agent behavior is controlled by `src/cuga/settings.toml` — key flags are under `[advanced_features]`: `mode` (`api`, `hybrid`), `api_planner_hitl`, `e2b_sandbox`
- Tool/API integrations are configured in `src/cuga/backend/tools_env/registry/config/mcp_servers.yaml`
- Slack integration requires `.env.slack` with `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, etc.

## Architecture

### Public SDK Entry Points

- `from cuga import CugaAgent, CugaSupervisor` — primary SDK classes, defined in `src/cuga/sdk.py`
- `cuga` CLI — entry point at `src/cuga/cli.py`
- FastAPI server — `src/cuga/backend/server/main.py` (started by `cuga start`)

### Core Agent Graph (`src/cuga/backend/cuga_graph/`)

Built on **LangGraph**. The graph is assembled in `graph.py` (`DynamicAgentGraph`). The execution loop lives in `utils/agent_loop.py` (`AgentLoop`).

Node groups (each in `nodes/`):
- **`task_decomposition_planning/`** — entry nodes: `TaskAnalyzerAgent` → `TaskDecompositionAgent` → `PlanControllerAgent`. The plan controller orchestrates the overall multi-step plan.
- **`api/`** — API sub-graph: `APIPlannerAgent` → `ShortlisterAgent` → `APICodePlannerAgent` → `CodeAgent`. Generates and executes Python code against registered APIs.
- **`browser/`** — Browser sub-graph: `BrowserPlannerAgent` → `ActionAgent` / `QaAgent`. Uses Playwright via BrowserGym.
- **`cuga_lite/`** — Lighter execution mode using direct tool calls (`CugaLiteNode`). Code execution via `executors/` (local restricted env or E2B sandbox).
- **`cuga_supervisor/`** — Multi-agent supervisor mode.
- **`human_in_the_loop/`** — `SuggestHumanActions` + `WaitForResponse` nodes for HITL approval gates.
- **`answer/`** — `FinalAnswerAgent` synthesizes the final response.
- **`save_reuse/`** — Captures successful runs as reusable deterministic Python.

Shared state is `AgentState` in `state/agent_state.py`. Variables produced by code execution are tracked by `VariablesManager` to prevent hallucination across steps.

### Tools Environment (`src/cuga/backend/tools_env/`)

- **Registry server** (`registry/`) — Standalone HTTP server (port 8001 by default) that exposes OpenAPI services, MCP servers, and TRM tools under a unified API. Configured via `config/mcp_servers.yaml`.
- **Code sandbox** (`code_sandbox/`) — Wraps `CodeExecutor`; supports local (restricted builtins) or E2B remote sandbox modes.

### Server (`src/cuga/backend/server/`)

FastAPI app (`main.py`) serving:
- Agent invocation and streaming SSE events
- Conversation history (SQLite via `conversation_history.py`)
- Config/secrets management routes
- Embedded frontend assets (React, in `src/frontend_workspaces/frontend/`)

### Integrations (`src/cuga/backend/integrations/`)

**Slack** (`slack/`): Webhook-based adapter that converts Slack events (app mentions, DMs, slash commands, interactive buttons) into CUGA events. Flow: `Slack → SlackEventHandler → CUGA Event Queue → Agent → SlackNotificationChannel → Slack`. Also supports Socket Mode for dev (no public URL needed).

### Policy System (`src/cuga/backend/cuga_graph/policy/`)

Five policy types configurable via SDK or UI: **IntentGuard** (block actions), **Playbook** (enforce workflows), **ToolApproval** (HITL gates), **ToolGuide** (inject domain context), **OutputFormatter** (transform responses). Policies are stored via `src/cuga/backend/storage/policy/`.

### Memory (`src/cuga/backend/memory/`)

Agentic memory using vector stores (Milvus/pgvector/sqlite-vec). Fact extraction, conflict resolution, and tips modules under `agentic_memory/llm/`.

### LLM Layer (`src/cuga/backend/llm/`)

`LLMManager` in `models.py` loads model config from the active TOML settings file. Supports OpenAI, WatsonX, Azure, Groq, Groq, OpenRouter, RITS, LiteLLM.

## Test Layout

```
tests/
  unit/          # Fast, no LLM calls — event models, session management, approval system
  integration/   # Require running services — tool call tracking, LLM config
  system/        # End-to-end — manager API integration
src/cuga/backend/cuga_graph/nodes/cuga_lite/executors/test_code_executor.py  # Executor tests
```

`pytest.ini_options` sets `asyncio_mode = "auto"` — all async tests work without explicit markers.
