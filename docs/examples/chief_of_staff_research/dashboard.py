"""Swarm dashboard for the chief_of_staff_research topology.

Starts a lightweight FastAPI server (default port 7860) that shows:
  - Agent cards with live status indicators
  - Structured tool-call activity feed (parsed from swarm.log)
  - Inter-agent dispatch stream
  - NOTIFY_SLACK post feed
  - Raw log stream with per-agent filtering
  - Link to Langfuse traces (if LANGFUSE_HOST is set)

Usage (standalone):
    python dashboard.py

Or launched automatically from run.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger

_TOPOLOGY = Path(__file__).parent / "topology.toml"
_LOG_FILE  = Path(__file__).parent / "logs" / "swarm.log"

app = FastAPI(title="CUGA Swarm Dashboard", docs_url=None, redoc_url=None)

# ---------------------------------------------------------------------------
# Log-line parsers — emit structured dicts for the /api/events stream
# ---------------------------------------------------------------------------

# [tool:web_searcher] ▶ web_search  input='...'
_RE_TOOL_START = re.compile(r"\[tool:([^\]]+)\] ▶ (\S+)\s+input=(.*)")
# [tool:web_searcher] ◀ '...'
_RE_TOOL_END   = re.compile(r"\[tool:([^\]]+)\] ◀ (.*)")
# [tool:web_searcher] ✗ ...
_RE_TOOL_ERR   = re.compile(r"\[tool:([^\]]+)\] ✗ (.*)")
# [dispatch] chief_of_staff → web_searcher (3582 chars)
_RE_DISPATCH   = re.compile(r"\[dispatch\] (\S+) → (\S+) \((\d+) chars\)")
# [swarm:web_searcher#2] processing (382 chars)
_RE_TASK_START = re.compile(r"\[swarm:([^#\]]+)#(\d+)\] processing \((\d+) chars\)")
# [swarm:web_searcher#2] timed out after 600s
_RE_TASK_TOUT  = re.compile(r"\[swarm:([^#\]]+)#(\d+)\] timed out after (\d+)s")
# [swarm:web_searcher#2] error: ...
_RE_TASK_ERR   = re.compile(r"\[swarm:([^#\]]+)#(\d+)\] error: (.*)")
# [swarm:chief_of_staff#1] ack posted to Slack
_RE_TASK_ACK   = re.compile(r"\[swarm:([^#\]]+)#(\d+)\] ack posted")
# NOTIFY_SLACK: or NOTIFY_SLACK:text  (appears in LLM response captured in log)
_RE_NOTIFY     = re.compile(r"NOTIFY_SLACK:(.*)")


def _parse_event(line: str) -> dict | None:
    """Return a structured event dict if the line matches a known pattern, else None."""
    # Strip loguru prefix: "YYYY-MM-DD HH:MM:SS.mmm | LEVEL    | [agent]           | "
    # Handles both old format (3 fields) and new format with agent column (4 fields).
    msg = re.sub(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| \S+\s+\| [^|]*\| ",
        "", line
    )
    if msg == line:
        # Fallback: strip old 3-field prefix
        msg = re.sub(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| \S+\s+\| ", "", line)

    m = _RE_TOOL_START.search(msg)
    if m:
        return {"type": "tool_start", "agent": m.group(1), "tool": m.group(2),
                "input": m.group(3)[:200]}

    m = _RE_TOOL_END.search(msg)
    if m:
        return {"type": "tool_end", "agent": m.group(1), "output": m.group(2)[:200]}

    m = _RE_TOOL_ERR.search(msg)
    if m:
        return {"type": "tool_error", "agent": m.group(1), "error": m.group(2)[:200]}

    m = _RE_DISPATCH.search(msg)
    if m:
        return {"type": "dispatch", "from": m.group(1), "to": m.group(2),
                "chars": int(m.group(3))}

    m = _RE_TASK_START.search(msg)
    if m:
        return {"type": "task_start", "agent": m.group(1), "index": m.group(2),
                "chars": int(m.group(3))}

    m = _RE_TASK_TOUT.search(msg)
    if m:
        return {"type": "task_timeout", "agent": m.group(1), "index": m.group(2),
                "seconds": int(m.group(3))}

    m = _RE_TASK_ERR.search(msg)
    if m:
        return {"type": "task_error", "agent": m.group(1), "index": m.group(2),
                "error": m.group(3)[:200]}

    m = _RE_TASK_ACK.search(msg)
    if m:
        return {"type": "task_ack", "agent": m.group(1), "index": m.group(2)}

    m = _RE_NOTIFY.search(msg)
    if m:
        text = m.group(1).strip()
        if text:
            return {"type": "notify", "text": text[:500]}

    return None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/topology")
def get_topology():
    import tomllib
    with open(_TOPOLOGY, "rb") as fh:
        raw = tomllib.load(fh)
    cfg = raw.get("configuration", {})
    agents = [
        {
            "id": a.get("id"),
            "role": a.get("role"),
            "domain": a.get("domain", ""),
            "peers": a.get("peers", []),
            "enable_knowledge": a.get("enable_knowledge", False),
            "mcp_servers": [s.get("name") for s in a.get("mcp_servers", [])],
            "timeout_seconds": a.get("timeout_seconds", 120),
        }
        for a in raw.get("agents", [])
    ]
    edges = [
        {"from": e.get("from"), "to": e.get("to"), "mode": e.get("mode")}
        for e in raw.get("edges", [])
    ]
    return {"name": cfg.get("name"), "pattern": cfg.get("pattern"),
            "agents": agents, "edges": edges}


@app.get("/api/logs")
async def stream_logs(agent: str = "") -> StreamingResponse:
    """SSE stream of raw swarm.log lines, optionally filtered."""
    return StreamingResponse(
        _tail_log(agent_filter=agent),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/events")
async def stream_events() -> StreamingResponse:
    """SSE stream of structured JSON events parsed from swarm.log."""
    return StreamingResponse(
        _tail_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _tail_log(agent_filter: str = "") -> AsyncGenerator[str, None]:
    _LOG_FILE.parent.mkdir(exist_ok=True)
    _LOG_FILE.touch(exist_ok=True)
    with open(_LOG_FILE, "r") as fh:
        for line in fh.readlines()[-200:]:
            if _matches(line, agent_filter):
                yield f"data: {line.rstrip()}\n\n"
        while True:
            line = fh.readline()
            if line:
                if _matches(line, agent_filter):
                    yield f"data: {line.rstrip()}\n\n"
            else:
                await asyncio.sleep(0.3)
                yield ": heartbeat\n\n"


async def _tail_events() -> AsyncGenerator[str, None]:
    _LOG_FILE.parent.mkdir(exist_ok=True)
    _LOG_FILE.touch(exist_ok=True)
    with open(_LOG_FILE, "r") as fh:
        # Replay last 500 lines as history
        for line in fh.readlines()[-500:]:
            ev = _parse_event(line)
            if ev:
                yield f"data: {json.dumps(ev)}\n\n"
        while True:
            line = fh.readline()
            if line:
                ev = _parse_event(line)
                if ev:
                    yield f"data: {json.dumps(ev)}\n\n"
            else:
                await asyncio.sleep(0.3)
                yield ": heartbeat\n\n"


def _matches(line: str, agent_filter: str) -> bool:
    """Match a raw log line against an agent filter.

    The log format (new, with agent column) is:
      YYYY-MM-DD HH:MM:SS.mmm | LEVEL    | <agent padded to 20> | message

    We match the agent column (parts[2] when split on ' | ') so that
    selecting 'web_searcher' doesn't also show lines where 'web_searcher'
    happens to appear in another agent's message body.

    Old-format lines (3 parts) fall back to a substring search.
    """
    if not agent_filter:
        return True
    parts = line.split(" | ", 3)   # at most 4 fields: time | level | agent | message
    if len(parts) >= 4:
        # parts[2] is the agent column (20-char padded)
        return agent_filter.lower() in parts[2].lower()
    # Fallback for old-format lines (no agent column)
    return agent_filter.lower() in line.lower()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CUGA Swarm Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e2e8f0; }

  header {
    display: flex; align-items: center; gap: 16px;
    padding: 14px 24px; background: #1a1f2e; border-bottom: 1px solid #2d3748;
  }
  header h1 { font-size: 1.2rem; font-weight: 600; }
  .badge {
    padding: 3px 10px; border-radius: 999px; font-size: 0.72rem;
    background: #2d3748; color: #a0aec0;
  }
  header .langfuse-link {
    margin-left: auto; font-size: 0.8rem; color: #63b3ed; text-decoration: none;
  }
  header .langfuse-link:hover { text-decoration: underline; }

  .section { padding: 16px 24px; }
  .section-title {
    font-size: 0.72rem; font-weight: 700; letter-spacing: .08em;
    text-transform: uppercase; color: #718096; margin-bottom: 10px;
    display: flex; align-items: center; gap: 8px;
  }

  /* ── Agent grid ─────────────────────────────────────────────────── */
  .agents { display: flex; flex-wrap: wrap; gap: 10px; }
  .agent-card {
    background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px;
    padding: 12px 14px; width: 210px; cursor: pointer;
    transition: border-color .15s, box-shadow .15s;
    position: relative;
  }
  .agent-card:hover, .agent-card.active { border-color: #63b3ed; }
  .agent-card.state-processing { border-color: #68d391; box-shadow: 0 0 8px #68d39133; }
  .agent-card.state-tool       { border-color: #f6ad55; box-shadow: 0 0 8px #f6ad5533; }
  .agent-card.state-error      { border-color: #fc8181; }

  .agent-card .card-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
  .agent-card .name { font-weight: 600; font-size: 0.9rem; flex: 1; }
  .agent-status-dot {
    width: 8px; height: 8px; border-radius: 50%; background: #4a5568;
    transition: background .3s;
    flex-shrink: 0;
  }
  .state-processing .agent-status-dot { background: #68d391; animation: pulse 1s infinite; }
  .state-tool       .agent-status-dot { background: #f6ad55; animation: pulse .6s infinite; }
  .state-error      .agent-status-dot { background: #fc8181; }

  .role-badge {
    display: inline-block; font-size: 0.68rem; padding: 1px 6px;
    border-radius: 999px; margin-bottom: 6px; font-weight: 600;
  }
  .role-entry  { background: #2b4c7e; color: #90cdf4; }
  .role-worker { background: #2d4a2d; color: #9ae6b4; }
  .role-exit   { background: #4a3020; color: #fbd38d; }
  .agent-card .domain { font-size: 0.72rem; color: #a0aec0; margin-bottom: 4px; }
  .agent-card .meta   { font-size: 0.68rem; color: #718096; }
  .agent-card .meta span { display: inline-block; margin-right: 5px; }
  .agent-card .current-tool {
    font-size: 0.68rem; color: #f6ad55; margin-top: 5px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .agent-card .task-count {
    position: absolute; top: 8px; right: 10px;
    font-size: 0.65rem; color: #63b3ed; font-weight: 700;
  }

  /* ── Dispatch + notify side-by-side ────────────────────────────── */
  .main-cols {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0;
    border-top: 1px solid #2d3748;
  }
  .main-cols .col-left  { border-right: 1px solid #2d3748; }

  .panel-header {
    display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  }
  .panel-header .section-title { margin-bottom: 0; flex: 1; }
  .panel-clear-btn {
    padding: 2px 9px; border-radius: 6px;
    background: #2d3748; border: none; color: #718096;
    cursor: pointer; font-size: 0.68rem;
    transition: color .15s, background .15s;
  }
  .panel-clear-btn:hover { background: #3d4a5e; color: #e2e8f0; }

  /* ── Dispatch stream ────────────────────────────────────────────── */
  #dispatch-feed {
    height: 200px; overflow-y: auto;
    font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.7rem;
    line-height: 1.6; padding: 0 4px;
  }
  .dispatch-row { display: flex; gap: 8px; align-items: center; }
  .dispatch-from { font-weight: 700; }
  .dispatch-arrow { color: #63b3ed; }
  .dispatch-to   { font-weight: 700; }
  .dispatch-chars { color: #718096; font-size: 0.65rem; }

  /* ── NOTIFY feed ────────────────────────────────────────────────── */
  #notify-feed {
    height: 200px; overflow-y: auto;
    font-size: 0.75rem; line-height: 1.5; padding: 0 4px;
  }
  .notify-row {
    padding: 5px 8px; margin-bottom: 4px;
    background: #1a2a1a; border-left: 3px solid #68d391; border-radius: 4px;
  }

  /* ── Raw log ────────────────────────────────────────────────────── */
  .log-bar {
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
  }
  .log-bar label { font-size: 0.72rem; color: #718096; }
  .log-bar select {
    background: #1a1f2e; border: 1px solid #2d3748; color: #e2e8f0;
    padding: 3px 7px; border-radius: 6px; font-size: 0.75rem;
  }
  .log-bar .clear-btn {
    margin-left: auto; padding: 3px 10px; border-radius: 6px;
    background: #2d3748; border: none; color: #a0aec0; cursor: pointer; font-size: 0.72rem;
  }
  #log-box {
    background: #0a0c12; border: 1px solid #2d3748; border-radius: 8px;
    height: 320px; overflow-y: auto; padding: 10px 12px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.69rem;
    line-height: 1.5;
  }
  .log-line { white-space: pre-wrap; word-break: break-all; }
  .log-INFO    { color: #a0aec0; }
  .log-WARNING { color: #f6ad55; }
  .log-ERROR   { color: #fc8181; }
  .log-DEBUG   { color: #4a5568; }
  .log-SUCCESS { color: #68d391; }
  .highlight   { background: #1a2a3a; border-radius: 2px; }

  /* ── Edges ──────────────────────────────────────────────────────── */
  .edges { display: flex; flex-wrap: wrap; gap: 7px; }
  .edge-pill {
    background: #1a1f2e; border: 1px solid #2d3748; border-radius: 999px;
    padding: 3px 10px; font-size: 0.72rem; color: #a0aec0;
  }
  .edge-pill .mode { color: #63b3ed; margin-left: 4px; }

  /* ── Status dot ─────────────────────────────────────────────────── */
  .status-dot {
    width: 7px; height: 7px; border-radius: 50%; background: #68d391;
    display: inline-block; margin-right: 5px; animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.4 } }

  /* ── Agent colour map (reused across panels) ─────────────────────── */
</style>
</head>
<body>

<header>
  <h1>🐝 CUGA Swarm</h1>
  <span class="badge" id="topology-name">loading…</span>
  <span class="badge" id="topology-pattern"></span>
  <span class="badge" id="event-count">0 events</span>
  <a class="langfuse-link" href="LANGFUSE_PLACEHOLDER/traces" target="_blank">📊 Langfuse ↗</a>
</header>

<!-- Agents -->
<div class="section">
  <div class="section-title">Agents</div>
  <div class="agents" id="agents-grid"></div>
</div>

<!-- Edges -->
<div class="section" id="edges-section" style="display:none">
  <div class="section-title">Declared edges</div>
  <div class="edges" id="edges-list"></div>
</div>

<!-- Dispatch + notify side by side -->
<div class="main-cols">
  <div class="col-left section">
    <div class="panel-header">
      <div class="section-title"><span class="status-dot"></span>Dispatches <span class="badge" id="dispatch-count">0</span></div>
      <button class="panel-clear-btn" onclick="clearDispatches()">Clear</button>
    </div>
    <div id="dispatch-feed"></div>
  </div>
  <div class="section">
    <div class="panel-header">
      <div class="section-title"><span class="status-dot"></span>Slack notifications <span class="badge" id="notify-count">0</span></div>
      <button class="panel-clear-btn" onclick="clearNotify()">Clear</button>
    </div>
    <div id="notify-feed"></div>
  </div>
</div>

<!-- Raw log -->
<div class="section" style="border-top:1px solid #2d3748">
  <div class="section-title">
    <span class="status-dot"></span>Raw log
  </div>
  <div class="log-bar">
    <label>Filter agent:</label>
    <select id="agent-filter" onchange="switchFilter(this.value)">
      <option value="">All agents</option>
    </select>
    <button class="clear-btn" onclick="clearLog()">Clear</button>
  </div>
  <div id="log-box"></div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let activeFilter = "";
let logEs = null;
let eventEs = null;
let totalEvents = 0;
let dispatchCount = 0;
let notifyCount = 0;

// agentState: { [id]: { state: 'idle'|'processing'|'tool', tool: str, tasks: int } }
const agentState = {};
// agent colour palette
const AGENT_COLORS = [
  "#63b3ed","#68d391","#f6ad55","#fc8181","#b794f4","#76e4f7","#fbb6ce","#faf089"
];
const agentColorMap = {};

function agentColor(id) {
  if (!agentColorMap[id]) {
    const idx = Object.keys(agentColorMap).length % AGENT_COLORS.length;
    agentColorMap[id] = AGENT_COLORS[idx];
  }
  return agentColorMap[id];
}

function colorSpan(id) {
  return `<span style="color:${agentColor(id)}">${id}</span>`;
}

// ── Topology ───────────────────────────────────────────────────────────────
function roleClass(role) {
  if (role === "entry") return "role-entry";
  if (role === "exit")  return "role-exit";
  return "role-worker";
}

async function loadTopology() {
  const res  = await fetch("/api/topology");
  const data = await res.json();

  document.getElementById("topology-name").textContent    = data.name;
  document.getElementById("topology-pattern").textContent = data.pattern;

  const grid = document.getElementById("agents-grid");
  const sel  = document.getElementById("agent-filter");

  data.agents.forEach(a => {
    agentState[a.id] = { state: "idle", tool: "", tasks: 0 };
    agentColor(a.id); // pre-assign colour

    const card = document.createElement("div");
    card.className    = "agent-card";
    card.id           = `card-${a.id}`;
    card.dataset.id   = a.id;
    card.onclick      = () => { sel.value = a.id; switchFilter(a.id); };

    const mcpBadge  = a.mcp_servers.length  ? `<span>🔌 ${a.mcp_servers.join(", ")}</span>` : "";
    const peerBadge = a.peers.length        ? `<span>🤝 ${a.peers.join(", ")}</span>`       : "";
    const kbBadge   = a.enable_knowledge    ? `<span>🧠 kb</span>`                          : "";
    const toStr     = `⏱ ${a.timeout_seconds}s`;

    card.innerHTML = `
      <span class="task-count" id="tasks-${a.id}"></span>
      <div class="card-header">
        <div class="name" style="color:${agentColor(a.id)}">${a.id}</div>
        <div class="agent-status-dot" id="dot-${a.id}"></div>
      </div>
      <span class="role-badge ${roleClass(a.role)}">${a.role}</span>
      <div class="domain">${a.domain || ""}</div>
      <div class="meta">${kbBadge}${mcpBadge}</div>
      <div class="meta">${peerBadge}<span>${toStr}</span></div>
      <div class="current-tool" id="ctool-${a.id}"></div>`;
    grid.appendChild(card);

    const opt = document.createElement("option");
    opt.value = a.id; opt.textContent = a.id;
    sel.appendChild(opt);
  });

  if (data.edges && data.edges.length) {
    document.getElementById("edges-section").style.display = "";
    const list = document.getElementById("edges-list");
    data.edges.forEach(e => {
      const pill = document.createElement("div");
      pill.className = "edge-pill";
      pill.innerHTML = `${colorSpan(e.from)} → ${colorSpan(e.to)}<span class="mode">${e.mode}</span>`;
      list.appendChild(pill);
    });
  }
}

// ── Agent card state updates ───────────────────────────────────────────────
function setAgentState(id, state, tool = "") {
  if (!agentState[id]) return;
  agentState[id].state = state;
  agentState[id].tool  = tool;
  const card = document.getElementById(`card-${id}`);
  if (!card) return;
  card.className = `agent-card${state !== "idle" ? " state-" + state : ""}`;
  const ctool = document.getElementById(`ctool-${id}`);
  if (ctool) ctool.textContent = tool ? `🔧 ${tool}` : "";
}

function incrementTasks(id) {
  if (!agentState[id]) return;
  agentState[id].tasks++;
  const el = document.getElementById(`tasks-${id}`);
  if (el) el.textContent = agentState[id].tasks > 0 ? `#${agentState[id].tasks}` : "";
}

// ── Structured event handler ───────────────────────────────────────────────
function handleEvent(ev) {
  totalEvents++;
  document.getElementById("event-count").textContent = `${totalEvents} events`;

  switch (ev.type) {

    case "task_start":
      setAgentState(ev.agent, "processing");
      incrementTasks(ev.agent);
      break;

    case "task_ack":
    case "task_timeout":
    case "task_error":
      setAgentState(ev.agent, "idle");
      break;

    case "tool_start":
      setAgentState(ev.agent, "tool", ev.tool);
      break;

    case "tool_end":
      if (agentState[ev.agent]?.state === "tool")
        setAgentState(ev.agent, "processing");
      break;

    case "tool_error":
      setAgentState(ev.agent, "processing");
      break;

    case "dispatch": {
      dispatchCount++;
      document.getElementById("dispatch-count").textContent = dispatchCount;
      const feed = document.getElementById("dispatch-feed");
      const row  = document.createElement("div");
      row.className = "dispatch-row";
      row.innerHTML =
        `<span class="dispatch-from" style="color:${agentColor(ev.from)}">${ev.from}</span>` +
        `<span class="dispatch-arrow">→</span>` +
        `<span class="dispatch-to" style="color:${agentColor(ev.to)}">${ev.to}</span>` +
        `<span class="dispatch-chars">${ev.chars} chars</span>`;
      feed.appendChild(row);
      feed.scrollTop = feed.scrollHeight;
      break;
    }

    case "notify": {
      notifyCount++;
      document.getElementById("notify-count").textContent = notifyCount;
      const feed = document.getElementById("notify-feed");
      const row  = document.createElement("div");
      row.className = "notify-row";
      row.textContent = ev.text;
      feed.appendChild(row);
      feed.scrollTop = feed.scrollHeight;
      break;
    }
  }
}

// ── Structured event SSE ───────────────────────────────────────────────────
let _eventEsConnected = false;

function clearDispatches() {
  document.getElementById("dispatch-feed").innerHTML = "";
  dispatchCount = 0;
  document.getElementById("dispatch-count").textContent = "0";
}

function clearNotify() {
  document.getElementById("notify-feed").innerHTML = "";
  notifyCount = 0;
  document.getElementById("notify-count").textContent = "0";
}

function clearLiveFeeds() {
  clearDispatches();
  clearNotify();
  totalEvents = 0;
  document.getElementById("event-count").textContent = "0 events";
  // Reset agent cards to idle
  Object.keys(agentState).forEach(id => setAgentState(id, "idle"));
}

function startEventStream() {
  if (eventEs) eventEs.close();
  _eventEsConnected = false;
  eventEs = new EventSource("/api/events");
  eventEs.onopen = () => {
    if (_eventEsConnected) {
      // Reconnect after a gap — server likely restarted
      clearLiveFeeds();
    }
    _eventEsConnected = true;
  };
  eventEs.onmessage = e => {
    try { handleEvent(JSON.parse(e.data)); } catch (_) {}
  };
  eventEs.onerror = () => {
    _eventEsConnected = false;
    setTimeout(startEventStream, 2000);
  };
}

// ── Raw log SSE ────────────────────────────────────────────────────────────
function levelClass(line) {
  if (line.includes("| ERROR"))   return "log-ERROR";
  if (line.includes("| WARNING")) return "log-WARNING";
  if (line.includes("| SUCCESS")) return "log-SUCCESS";
  if (line.includes("| DEBUG"))   return "log-DEBUG";
  return "log-INFO";
}

function appendLogLine(text) {
  const box = document.getElementById("log-box");
  const div = document.createElement("div");
  div.className = "log-line " + levelClass(text);
  if (activeFilter && text.toLowerCase().includes(activeFilter.toLowerCase()))
    div.classList.add("highlight");
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function startStream(filter) {
  if (logEs) logEs.close();
  document.getElementById("log-box").innerHTML = "";
  activeFilter = filter;
  const url = "/api/logs" + (filter ? "?agent=" + encodeURIComponent(filter) : "");
  logEs = new EventSource(url);
  logEs.onmessage = e => appendLogLine(e.data);
  logEs.onerror   = () => setTimeout(() => startStream(filter), 2000);
}

function switchFilter(val) {
  startStream(val);
  document.querySelectorAll(".agent-card").forEach(c => {
    c.classList.toggle("active", c.dataset.id === val && val !== "");
  });
}

function clearLog() { document.getElementById("log-box").innerHTML = ""; }

function escHtml(s) {
  return String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Boot ───────────────────────────────────────────────────────────────────
loadTopology();
startStream("");
startEventStream();
</script>
</body>
</html>
""".replace("LANGFUSE_PLACEHOLDER", _LANGFUSE_HOST)


@app.get("/", response_class=HTMLResponse)
def index():
    return _HTML


# ---------------------------------------------------------------------------
# Standalone entry
# ---------------------------------------------------------------------------

async def start(host: str = "0.0.0.0", port: int = 7860):
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    logger.info(f"Dashboard → http://localhost:{port}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(start())
