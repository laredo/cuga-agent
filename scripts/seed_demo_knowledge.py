"""
Seed the CUGA knowledge base with demo entries for the PM Bulletin demo.

Run this once before the demo (with cuga start running in another terminal):
    uv run python scripts/seed_demo_knowledge.py

Seeds 3 entries representing product updates Maya has accumulated over the week.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

import httpx

BASE_URL = "http://localhost:7860"

SEED_ENTRIES = [
    {
        "filename": "cuga-v34-async-exports.md",
        "content": """\
# CUGA v3.4 — Async Export Engine

**Released:** 2026-05-01

## What shipped

CUGA's report generation is now fully asynchronous. Large exports that previously
blocked the UI for 2–5 minutes now run in the background and notify the user when ready.

Key metrics from internal testing:
- Average wait time reduced from 3.2 minutes to under 5 seconds (perceived)
- Supports exports up to 500k rows without timeout
- Compatible with PDF, CSV, and Excel output formats

This feature was the #1 customer request in Q1 2026.
""",
    },
    {
        "filename": "cuga-v34-skill-marketplace.md",
        "content": """\
# CUGA v3.4 — Skill Marketplace (Beta)

**Released:** 2026-05-03

## What shipped

Users can now browse, install, and share automation skills directly from the CUGA UI.
Skills are self-contained bundles (SKILL.md + policies + knowledge) that extend the agent's
capabilities without requiring engineering involvement.

Launch catalog includes:
- Timesheet automation (HR)
- Weekly bulletin generator (Communications)
- Knowledge capture from Slack forwards (Productivity)
- Expense report drafting (Finance)

Skills are sandboxed — each runs under its own policy scope.
""",
    },
    {
        "filename": "cuga-v34-nl-scheduling.md",
        "content": """\
# CUGA v3.4 — Natural Language Scheduling

**Released:** 2026-05-05

## What shipped

Users can now schedule any skill using plain English. No cron syntax required.

Examples:
- "Every Friday at 4pm, draft the customer bulletin"
- "Remind me to review pipeline metrics every Monday morning"
- "Run the expense report on the last day of the month"

The scheduler parses intent into a cron expression, confirms with the user,
and persists the job. Jobs survive server restarts (persistent storage).
""",
    },
]


async def ingest_text(client: httpx.AsyncClient, filename: str, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", prefix=filename.replace(".md", "-"), delete=False
    ) as f:
        f.write(content)
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            resp = await client.post(
                "/api/knowledge/documents",
                files={"files": (filename, f, "text/markdown")},
                data={"scope": "agent", "replace_duplicates": "true"},
                headers={"X-Agent-ID": "cuga-default"},
                timeout=30.0,
            )
        resp.raise_for_status()
        result = resp.json()
        task_id = result.get("task_id", result.get("results", [{}])[0].get("task_id", "?"))
        print(f"  ✓ {filename} — task_id: {task_id}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def main() -> None:
    print(f"Seeding CUGA knowledge base at {BASE_URL}...\n")

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        try:
            resp = await client.get("/health", timeout=5.0)
            resp.raise_for_status()
        except Exception:
            print(f"ERROR: Could not reach {BASE_URL}. Is 'cuga start' running?")
            sys.exit(1)

        for entry in SEED_ENTRIES:
            await ingest_text(client, entry["filename"], entry["content"])

    print(f"\nDone. {len(SEED_ENTRIES)} entries ingested into scope='agent'.")
    print("Maya can now ask: 'What did we ship recently?' and get a real answer.")


if __name__ == "__main__":
    asyncio.run(main())
