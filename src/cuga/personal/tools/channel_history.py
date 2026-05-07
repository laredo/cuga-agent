"""Slack channel history: fetch, chunk by day, summarize, and store digests."""

from __future__ import annotations

import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
from langchain_core.tools import tool

_SLACK_API = "https://slack.com/api"
_BACKEND_URL = os.environ.get("CUGA_BACKEND_URL", "http://localhost:7860").rstrip("/")
_AGENT_ID = "cuga-default"
_SCOPE = "agent"
_MAX_PER_CHUNK = 150


# ---------------------------------------------------------------------------
# Slack API helpers
# ---------------------------------------------------------------------------


def _slack_headers() -> Dict[str, str]:
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set")
    return {"Authorization": f"Bearer {token}"}


def _get_channel_name(channel_id: str) -> str:
    """Resolve a channel ID to its human-readable name."""
    try:
        with httpx.Client(base_url=_SLACK_API, headers=_slack_headers(), timeout=10.0) as c:
            resp = c.get("/conversations.info", params={"channel": channel_id})
            data = resp.json()
            if data.get("ok"):
                return data["channel"].get("name", channel_id)
    except Exception:
        pass
    return channel_id


def _fetch_messages(channel_id: str, oldest_ts: float) -> List[Dict[str, Any]]:
    """Paginate conversations.history and return all non-bot messages, oldest-first."""
    messages: List[Dict[str, Any]] = []
    params: Dict[str, Any] = {"channel": channel_id, "oldest": str(oldest_ts), "limit": 200}

    with httpx.Client(base_url=_SLACK_API, headers=_slack_headers(), timeout=30.0) as c:
        while True:
            resp = c.get("/conversations.history", params=params)
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")

            for msg in data.get("messages", []):
                if not msg.get("subtype") and not msg.get("bot_id"):
                    messages.append(msg)

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor

    return sorted(messages, key=lambda m: float(m["ts"]))


def _resolve_usernames(messages: List[Dict[str, Any]]) -> Dict[str, str]:
    """Return a uid → display_name map for all users in the message list."""
    uids = {m.get("user") for m in messages if m.get("user")}
    names: Dict[str, str] = {}
    with httpx.Client(base_url=_SLACK_API, headers=_slack_headers(), timeout=10.0) as c:
        for uid in uids:
            resp = c.get("/users.info", params={"user": uid})
            data = resp.json()
            if data.get("ok"):
                profile = data["user"].get("profile", {})
                names[uid] = profile.get("display_name") or profile.get("real_name") or uid
            else:
                names[uid] = uid
    return names


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _chunk_by_day(
    messages: List[Dict[str, Any]],
    max_per_chunk: int = _MAX_PER_CHUNK,
) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Group messages by UTC calendar date. Split days exceeding max_per_chunk."""
    by_day: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for msg in messages:
        day = datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc).strftime("%Y-%m-%d")
        by_day[day].append(msg)

    chunks: List[Tuple[str, List[Dict[str, Any]]]] = []
    for day in sorted(by_day):
        day_msgs = by_day[day]
        if len(day_msgs) <= max_per_chunk:
            chunks.append((day, day_msgs))
        else:
            n_parts = -(-len(day_msgs) // max_per_chunk)  # ceil div
            for i in range(n_parts):
                label = f"{day} (part {i + 1}/{n_parts})"
                chunks.append((label, day_msgs[i * max_per_chunk : (i + 1) * max_per_chunk]))

    return chunks


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------


def _format_chunk(day: str, messages: List[Dict[str, Any]], names: Dict[str, str]) -> str:
    lines = [f"# Slack messages — {day}\n"]
    for msg in messages:
        ts = datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc).strftime("%H:%M")
        user = names.get(msg.get("user", ""), "unknown")
        text = msg.get("text", "").strip()
        if text:
            lines.append(f"[{ts}] {user}: {text}")
    return "\n".join(lines)


def _summarize_chunk(formatted_text: str) -> str:
    """Summarize one day's messages. Uses OpenAI if available, else extractive fallback."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        lines = [l for l in formatted_text.splitlines() if l.strip() and not l.startswith("#")]
        head = lines[:5]
        tail = lines[-3:] if len(lines) > 8 else []
        note = f"[{len(lines)} messages — OPENAI_API_KEY not set, showing excerpt only]"
        return "\n".join(head + (["..."] if tail else []) + tail + [note])

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        prompt = (
            "Summarize the following Slack conversation into 3–6 bullet points. "
            "Focus on: decisions made, announcements, questions raised, action items. "
            "Be concise. Skip off-topic chatter.\n\n"
            + formatted_text
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"[Summarization error: {exc}]"


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _store_digest(day: str, channel_name: str, summary: str) -> None:
    """Write a day's digest to the knowledge backend."""
    title = f"channel-digest-{channel_name}-{day}"
    content = f"# {title}\n\n**Channel:** #{channel_name}\n**Date:** {day}\n\n{summary}\n"
    filename = title[:60] + ".md"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", prefix="cuga-digest-", delete=False) as f:
        f.write(content)
        tmp = f.name

    try:
        headers = {"X-Agent-ID": _AGENT_ID}
        with httpx.Client(base_url=_BACKEND_URL, headers=headers, timeout=30.0) as c, open(tmp, "rb") as fh:
            c.post(
                "/api/knowledge/documents",
                files={"files": (filename, fh, "text/markdown")},
                data={"scope": _SCOPE, "replace_duplicates": "true"},
            )
    finally:
        Path(tmp).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# LangChain tool
# ---------------------------------------------------------------------------


@tool
def fetch_and_digest_channel(
    channel_id: str,
    lookback_days: int = 30,
    channel_name: str = "",
) -> str:
    """Fetch messages from a Slack channel, summarize each day, and store digests in the knowledge base.

    Args:
        channel_id: Slack channel ID (e.g. C12345678)
        lookback_days: How many days back to fetch (default: 30)
        channel_name: Human-readable name for storage labels; auto-resolved if omitted
    """
    try:
        _slack_headers()  # validate token early
    except RuntimeError as e:
        return str(e)

    name = channel_name or _get_channel_name(channel_id)
    oldest_ts = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp()

    try:
        messages = _fetch_messages(channel_id, oldest_ts)
    except RuntimeError as e:
        return f"Failed to fetch #{name} history: {e}"

    if not messages:
        return f"No messages found in #{name} for the past {lookback_days} day(s)."

    names = _resolve_usernames(messages)
    chunks = _chunk_by_day(messages)

    report_lines: List[str] = []
    for day, day_msgs in chunks:
        formatted = _format_chunk(day, day_msgs, names)
        summary = _summarize_chunk(formatted)
        _store_digest(day, name, summary)
        report_lines.append(f"• {day}: {len(day_msgs)} message(s) → digest stored")

    return (
        f"Channel digest complete — #{name}\n\n"
        f"Processed {len(messages)} messages across {len(chunks)} day chunk(s):\n"
        + "\n".join(report_lines)
        + "\n\nAll digests are searchable in the knowledge base."
    )


def get_channel_history_tools() -> list:
    return [fetch_and_digest_channel]
