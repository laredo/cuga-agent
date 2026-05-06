"""LangChain tool wrappers that call the CUGA knowledge HTTP API at localhost:7860.

Used by the personal orchestrator's CugaAgent so it can read/write the same
knowledge store as the running backend without trying to start a second engine.
"""

import os
from typing import List

import httpx
from langchain_core.tools import tool

_BACKEND_URL = os.environ.get("CUGA_BACKEND_URL", "http://localhost:7860").rstrip("/")
_AGENT_ID = "cuga-default"
_SCOPE = "agent"
_HEADERS = {"X-Agent-ID": _AGENT_ID}
_TIMEOUT = 30.0


def _client() -> httpx.Client:
    return httpx.Client(base_url=_BACKEND_URL, headers=_HEADERS, timeout=_TIMEOUT)


@tool
def search_knowledge(query: str) -> str:
    """Search the agent knowledge base for information matching the query.
    Returns relevant text excerpts with source filenames."""
    with _client() as c:
        resp = c.post("/api/knowledge/search", json={"scope": _SCOPE, "query": query})
        if resp.status_code != 200:
            return f"Search failed: {resp.status_code} {resp.text}"
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return "No results found in knowledge base."
        lines = []
        for r in results:
            src = r.get("filename", "unknown")
            lines.append(f"[{src}] {r.get('text', '').strip()}")
        return "\n\n".join(lines)


@tool
def ingest_knowledge_url(url: str) -> str:
    """Ingest a web page or document from a URL into the agent knowledge base.
    The content will be available for future searches."""
    with _client() as c:
        resp = c.post("/api/knowledge/documents/url", json={"scope": _SCOPE, "url": url})
        if resp.status_code != 200:
            return f"Ingestion failed: {resp.status_code} {resp.text}"
        data = resp.json()
        task_id = data.get("task_id", "?")
        status = data.get("status", "queued")
        return f"Stored (task_id: {task_id}, status: {status}). The content will be searchable shortly."


@tool
def ingest_knowledge_text(text: str, title: str = "note") -> str:
    """Store a plain-text note or snippet into the agent knowledge base.
    Use this when the user wants to save text (not a URL)."""
    import tempfile
    from pathlib import Path

    filename = title.lower().replace(" ", "-")[:40] + ".md"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", prefix="cuga-note-", delete=False
    ) as f:
        f.write(f"# {title}\n\n{text}\n")
        tmp_path = f.name

    try:
        with _client() as c, open(tmp_path, "rb") as fh:
            resp = c.post(
                "/api/knowledge/documents",
                files={"files": (filename, fh, "text/markdown")},
                data={"scope": _SCOPE, "replace_duplicates": "true"},
            )
        if resp.status_code != 200:
            return f"Ingestion failed: {resp.status_code} {resp.text}"
        data = resp.json()
        results = data.get("results", [data])
        task_id = results[0].get("task_id", "?") if results else "?"
        return f"Stored '{title}' (task_id: {task_id}). Searchable shortly."
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def get_knowledge_tools() -> List:
    """Return all knowledge tools for injection into CugaAgent."""
    return [search_knowledge, ingest_knowledge_url, ingest_knowledge_text]
