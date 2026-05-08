"""Swarm dashboard for the chief_of_staff_research topology.

Starts a lightweight FastAPI server (default port 7860) that shows:
  - Agent cards (id, role, domain, peers) loaded from topology.toml
  - A live log stream with per-agent filtering
  - A link to Langfuse traces (if LANGFUSE_HOST is set)

Usage (standalone):
    python dashboard.py

Or launched automatically from run.py.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger

_TOPOLOGY = Path(__file__).parent / "topology.toml"
_LOG_FILE = Path(__file__).parent / "logs" / "swarm.log"

app = FastAPI(title="CUGA Swarm Dashboard", docs_url=None, redoc_url=None)

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
        }
        for a in raw.get("agents", [])
    ]
    edges = [
        {"from": e.get("from"), "to": e.get("to"), "mode": e.get("mode")}
        for e in raw.get("edges", [])
    ]
    return {"name": cfg.get("name"), "pattern": cfg.get("pattern"), "agents": agents, "edges": edges}


@app.get("/api/logs")
async def stream_logs(agent: str = "") -> StreamingResponse:
    """SSE stream of swarm.log, optionally filtered to lines containing `agent`."""
    return StreamingResponse(
        _tail_log(agent_filter=agent),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _tail_log(agent_filter: str = "") -> AsyncGenerator[str, None]:
    _LOG_FILE.parent.mkdir(exist_ok=True)
    _LOG_FILE.touch(exist_ok=True)

    with open(_LOG_FILE, "r") as fh:
        # Send last 200 lines as history
        lines = fh.readlines()
        for line in lines[-200:]:
            if _matches(line, agent_filter):
                yield f"data: {line.rstrip()}\n\n"

        # Tail new lines
        while True:
            line = fh.readline()
            if line:
                if _matches(line, agent_filter):
                    yield f"data: {line.rstrip()}\n\n"
            else:
                await asyncio.sleep(0.3)
                yield ": heartbeat\n\n"


def _matches(line: str, agent_filter: str) -> bool:
    return not agent_filter or agent_filter.lower() in line.lower()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CUGA Swarm Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f1117; color: #e2e8f0; }

  header {
    display: flex; align-items: center; gap: 16px;
    padding: 16px 24px; background: #1a1f2e; border-bottom: 1px solid #2d3748;
  }
  header h1 { font-size: 1.25rem; font-weight: 600; }
  header .badge {
    padding: 3px 10px; border-radius: 999px; font-size: 0.75rem;
    background: #2d3748; color: #a0aec0;
  }
  header .langfuse-link {
    margin-left: auto; font-size: 0.8rem;
    color: #63b3ed; text-decoration: none;
  }
  header .langfuse-link:hover { text-decoration: underline; }

  .section { padding: 20px 24px; }
  .section-title { font-size: 0.75rem; font-weight: 700; letter-spacing: .08em;
    text-transform: uppercase; color: #718096; margin-bottom: 12px; }

  /* Agent grid */
  .agents { display: flex; flex-wrap: wrap; gap: 12px; }
  .agent-card {
    background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px;
    padding: 14px 16px; width: 220px; cursor: pointer; transition: border-color .15s;
  }
  .agent-card:hover, .agent-card.active { border-color: #63b3ed; }
  .agent-card .name { font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; }
  .agent-card .role-badge {
    display: inline-block; font-size: 0.7rem; padding: 1px 7px;
    border-radius: 999px; margin-bottom: 8px; font-weight: 600;
  }
  .role-entry  { background: #2b4c7e; color: #90cdf4; }
  .role-worker { background: #2d4a2d; color: #9ae6b4; }
  .role-exit   { background: #4a3020; color: #fbd38d; }
  .agent-card .domain { font-size: 0.75rem; color: #a0aec0; margin-bottom: 6px; }
  .agent-card .meta { font-size: 0.7rem; color: #718096; }
  .agent-card .meta span { display: inline-block; margin-right: 6px; }

  /* Edges */
  .edges { display: flex; flex-wrap: wrap; gap: 8px; }
  .edge-pill {
    background: #1a1f2e; border: 1px solid #2d3748; border-radius: 999px;
    padding: 4px 12px; font-size: 0.75rem; color: #a0aec0;
  }
  .edge-pill .mode { color: #63b3ed; margin-left: 4px; }

  /* Log panel */
  .log-bar {
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
  }
  .log-bar label { font-size: 0.75rem; color: #718096; }
  .log-bar select {
    background: #1a1f2e; border: 1px solid #2d3748; color: #e2e8f0;
    padding: 4px 8px; border-radius: 6px; font-size: 0.8rem;
  }
  .log-bar .clear-btn {
    margin-left: auto; padding: 4px 12px; border-radius: 6px;
    background: #2d3748; border: none; color: #a0aec0; cursor: pointer; font-size: 0.75rem;
  }
  #log-box {
    background: #0a0c12; border: 1px solid #2d3748; border-radius: 8px;
    height: 420px; overflow-y: auto; padding: 12px 14px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.72rem;
    line-height: 1.55;
  }
  .log-line { white-space: pre-wrap; word-break: break-all; }
  .log-INFO    { color: #a0aec0; }
  .log-WARNING { color: #f6ad55; }
  .log-ERROR   { color: #fc8181; }
  .log-DEBUG   { color: #718096; }
  .log-SUCCESS { color: #68d391; }
  .highlight   { background: #2d4a2d; border-radius: 2px; }

  /* Status dot */
  .status-dot {
    width: 8px; height: 8px; border-radius: 50%; background: #68d391;
    display: inline-block; margin-right: 6px; animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:.4 } }
</style>
</head>
<body>

<header>
  <h1>🐝 CUGA Swarm</h1>
  <span class="badge" id="topology-name">loading…</span>
  <span class="badge" id="topology-pattern"></span>
  <a class="langfuse-link" href="LANGFUSE_HOST_PLACEHOLDER/traces" target="_blank">
    📊 Langfuse traces ↗
  </a>
</header>

<div class="section">
  <div class="section-title">Agents</div>
  <div class="agents" id="agents-grid"></div>
</div>

<div class="section" id="edges-section" style="display:none">
  <div class="section-title">Declared edges</div>
  <div class="edges" id="edges-list"></div>
</div>

<div class="section">
  <div class="section-title">
    <span class="status-dot"></span>Live log
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
let activeFilter = "";
let es = null;

function levelClass(line) {
  if (line.includes("| ERROR")) return "log-ERROR";
  if (line.includes("| WARNING")) return "log-WARNING";
  if (line.includes("| SUCCESS")) return "log-SUCCESS";
  if (line.includes("| DEBUG")) return "log-DEBUG";
  return "log-INFO";
}

function appendLine(text) {
  const box = document.getElementById("log-box");
  const div = document.createElement("div");
  div.className = "log-line " + levelClass(text);
  if (activeFilter && text.toLowerCase().includes(activeFilter.toLowerCase())) {
    div.classList.add("highlight");
  }
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function startStream(filter) {
  if (es) es.close();
  document.getElementById("log-box").innerHTML = "";
  activeFilter = filter;
  const url = "/api/logs" + (filter ? "?agent=" + encodeURIComponent(filter) : "");
  es = new EventSource(url);
  es.onmessage = e => appendLine(e.data);
  es.onerror = () => setTimeout(() => startStream(filter), 2000);
}

function switchFilter(val) {
  startStream(val);
  document.querySelectorAll(".agent-card").forEach(c => c.classList.remove("active"));
  if (val) {
    document.querySelectorAll(".agent-card").forEach(c => {
      if (c.dataset.id === val) c.classList.add("active");
    });
  }
}

function clearLog() { document.getElementById("log-box").innerHTML = ""; }

function roleClass(role) {
  if (role === "entry") return "role-entry";
  if (role === "exit")  return "role-exit";
  return "role-worker";
}

async function loadTopology() {
  const res = await fetch("/api/topology");
  const data = await res.json();

  document.getElementById("topology-name").textContent = data.name;
  document.getElementById("topology-pattern").textContent = data.pattern;

  const grid = document.getElementById("agents-grid");
  const sel  = document.getElementById("agent-filter");

  data.agents.forEach(a => {
    // Card
    const card = document.createElement("div");
    card.className = "agent-card";
    card.dataset.id = a.id;
    card.onclick = () => { sel.value = a.id; switchFilter(a.id); };
    const mcpBadge = a.mcp_servers.length ? `<span>🔌 ${a.mcp_servers.join(", ")}</span>` : "";
    const kbBadge  = a.enable_knowledge ? `<span>🧠 kb</span>` : "";
    const peerBadge = a.peers.length ? `<span>🤝 ${a.peers.join(", ")}</span>` : "";
    card.innerHTML = `
      <div class="name">${a.id}</div>
      <span class="role-badge ${roleClass(a.role)}">${a.role}</span>
      <div class="domain">${a.domain || ""}</div>
      <div class="meta">${kbBadge}${mcpBadge}</div>
      <div class="meta">${peerBadge}</div>`;
    grid.appendChild(card);

    // Filter option
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = a.id;
    sel.appendChild(opt);
  });

  // Edges
  if (data.edges && data.edges.length) {
    document.getElementById("edges-section").style.display = "";
    const list = document.getElementById("edges-list");
    data.edges.forEach(e => {
      const pill = document.createElement("div");
      pill.className = "edge-pill";
      pill.innerHTML = `${e.from} → ${e.to}<span class="mode">${e.mode}</span>`;
      list.appendChild(pill);
    });
  }
}

loadTopology();
startStream("");
</script>
</body>
</html>
""".replace("LANGFUSE_HOST_PLACEHOLDER", _LANGFUSE_HOST)


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
