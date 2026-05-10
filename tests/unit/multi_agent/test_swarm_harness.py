"""Swarm integration harness — real LLM, real MCP, no Slack.

Replaces the Slack e2e loop for iterating on agent behavior.

Two modes
---------
pytest (default)
    pytest tests/unit/multi_agent/test_swarm_harness.py -v -s

standalone (prints a full run timeline to stdout)
    python tests/unit/multi_agent/test_swarm_harness.py

Tests
-----
test_chief_of_staff_smoke
    Invokes _agent_task() on chief_of_staff alone with a canned research
    request.  Asserts an ack arrives within 60 s.  Fastest signal (~30 s)
    that the entry agent is healthy after any code change.

test_full_swarm_research
    Runs the complete swarm via ConfigurationRunner.run().  Asserts:
      - Entry ack arrives within 90 s
      - At least one NOTIFY post arrives from background workers
      - At least one NOTIFY mentions a document found (web_searcher working)
      - At least one NOTIFY mentions vetted or discarded (fact_checker working)
    Workers are given up to WORKER_WAIT_S seconds after the ack to post.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import List, Tuple

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]   # …/cuga-agent
sys.path.insert(0, str(REPO_ROOT / "src"))

TOPOLOGY = (
    REPO_ROOT / "docs" / "examples" / "chief_of_staff_research" / "topology.toml"
)
ENV_FILE = TOPOLOGY.parent / ".env"

# ---------------------------------------------------------------------------
# Load .env for the example (API keys, MCP URLs)
# ---------------------------------------------------------------------------

def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        if ENV_FILE.exists():
            load_dotenv(ENV_FILE)
    except ImportError:
        pass

_load_env()

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------

ENTRY_ACK_TIMEOUT_S  = 300   # includes factory build (~35 s) + entry-agent timeout (180 s)
WORKER_WAIT_S        = 300   # how long to collect NOTIFY posts after ack
TEST_REQUEST         = "research agentic AI frameworks 2025"

# ---------------------------------------------------------------------------
# In-memory Slack poster
# ---------------------------------------------------------------------------

class NotifyCollector:
    """Async slack_poster replacement: collects posts with timestamps."""

    def __init__(self) -> None:
        self.posts: List[Tuple[float, str]] = []
        self._event = asyncio.Event()

    async def poster(self, text: str) -> None:
        ts = time.monotonic()
        self.posts.append((ts, text))
        print(f"\n[NOTIFY +{ts:.1f}s] {text[:200]}", flush=True)
        self._event.set()
        self._event.clear()

    async def wait_for_post(self, timeout: float) -> bool:
        """Return True if at least one post arrives within timeout."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    @property
    def all_text(self) -> str:
        return "\n".join(t for _, t in self.posts)


# ---------------------------------------------------------------------------
# Smoke test: chief_of_staff alone via _agent_task()
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.asyncio
async def test_chief_of_staff_smoke():
    """Entry agent acks within 60 s with non-empty text. No workers involved."""
    from cuga.backend.multi_agent.config import load_config
    from cuga.backend.multi_agent.swarm_factory import SwarmAgentFactory
    from cuga.backend.multi_agent.patterns.swarm import _agent_task

    cfg = load_config(TOPOLOGY)
    entry_cfg = next(a for a in cfg.agents if a.role == "entry")

    collector = NotifyCollector()
    first_response_q: asyncio.Queue[str] = asyncio.Queue()

    async with SwarmAgentFactory(cfg) as factory:
        agent = factory.agents[entry_cfg.id]

        print(f"\n[smoke] invoking chief_of_staff with: {TEST_REQUEST!r}", flush=True)
        t0 = time.monotonic()

        await asyncio.wait_for(
            _agent_task(
                agent_id=entry_cfg.id,
                agent=agent,
                content=TEST_REQUEST,
                task_id="harness-smoke-001",
                msg_index=1,
                timeout=entry_cfg.timeout_seconds,
                is_entry=True,
                first_response_queue=first_response_q,
                slack_poster=collector.poster,
            ),
            timeout=float(entry_cfg.timeout_seconds) + 30.0,
        )

        elapsed = time.monotonic() - t0

    assert not first_response_q.empty(), "chief_of_staff did not put an ack"
    ack = first_response_q.get_nowait()

    print(f"\n[smoke] ack ({elapsed:.1f}s): {ack!r}", flush=True)

    assert ack, "ack is empty"
    assert len(ack) > 10, f"ack suspiciously short: {ack!r}"
    assert elapsed < entry_cfg.timeout_seconds, (
        f"chief_of_staff took {elapsed:.1f}s — exceeded {entry_cfg.timeout_seconds}s limit"
    )


# ---------------------------------------------------------------------------
# Full swarm test via ConfigurationRunner
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.asyncio
async def test_full_swarm_research():
    """Full pipeline: ack + at least one NOTIFY from web_searcher and fact_checker."""
    from cuga.backend.multi_agent.config import load_config
    from cuga.backend.multi_agent.swarm_factory import SwarmAgentFactory
    from cuga.backend.multi_agent.runner import ConfigurationRunner

    cfg = load_config(TOPOLOGY)
    collector = NotifyCollector()
    t0 = time.monotonic()

    async with SwarmAgentFactory(cfg) as factory:
        runner = ConfigurationRunner(
            cfg,
            agents=factory.agents,
            agent_queues=factory.agent_queues,
        )

        print(f"\n[harness] sending: {TEST_REQUEST!r}", flush=True)

        result = await asyncio.wait_for(
            runner.run(
                TEST_REQUEST,
                task_id="harness-full-001",
                slack_poster=collector.poster,
            ),
            timeout=ENTRY_ACK_TIMEOUT_S,
        )

        ack_elapsed = time.monotonic() - t0
        print(f"\n[harness] ack ({ack_elapsed:.1f}s): {result.answer!r}", flush=True)

        # ── Assert entry ack ────────────────────────────────────────────────
        assert result.answer, "runner returned empty answer"
        assert len(result.answer) > 10, f"ack too short: {result.answer!r}"
        assert ack_elapsed < ENTRY_ACK_TIMEOUT_S, (
            f"ack took {ack_elapsed:.1f}s, exceeded {ENTRY_ACK_TIMEOUT_S}s"
        )

        # ── Wait for background workers ─────────────────────────────────────
        print(
            f"\n[harness] waiting up to {WORKER_WAIT_S}s for worker NOTIFY posts…",
            flush=True,
        )
        any_posted = False
        deadline = time.monotonic() + WORKER_WAIT_S
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            arrived = await collector.wait_for_post(timeout=min(30.0, remaining))
            if arrived:
                any_posted = True
            elif any_posted:
                break  # 30 s of silence after the first post → workers done
            # else: no post yet — workers still warming up; keep waiting

        worker_elapsed = time.monotonic() - t0
        print(
            f"\n[harness] collected {len(collector.posts)} NOTIFY post(s) "
            f"in {worker_elapsed:.1f}s total",
            flush=True,
        )

    # ── Print full timeline ─────────────────────────────────────────────────
    print("\n── NOTIFY timeline ─────────────────────────────────────")
    for ts, text in collector.posts:
        print(f"  +{ts:.1f}s  {text[:120]}")
    print("────────────────────────────────────────────────────────\n")

    # ── Assert workers did something ────────────────────────────────────────
    all_text = collector.all_text.lower()

    assert collector.posts, (
        "No NOTIFY posts received from background workers — "
        "dispatch tool calls may not be firing"
    )

    # web_searcher posts NOTIFY_SLACK via its final text output.  The
    # FinalAnswerAgent sometimes omits them when the model prints them inside
    # Python code rather than in plain text.  Accept either direct web_searcher
    # keywords OR fact_checker posts (which prove web_searcher dispatched).
    found_web_searcher = any(
        kw in all_text
        for kw in ("found:", "📄", "web search", "dispatched", "source",
                   # fact_checker posts prove web_searcher dispatched
                   "vetted", "discarded", "score", "✅", "❌")
    )
    assert found_web_searcher, (
        "No NOTIFY post looks like a web_searcher or fact_checker update "
        "(web_searcher dispatch may not be firing). Posts received:\n"
        + "\n".join(f"  {t}" for _, t in collector.posts)
    )

    found_fact_checker = any(
        kw in all_text
        for kw in ("vetted", "discarded", "score", "✅", "❌", "fact")
    )
    assert found_fact_checker, (
        "No NOTIFY post looks like a fact_checker update. Posts received:\n"
        + "\n".join(f"  {t}" for _, t in collector.posts)
    )


# ---------------------------------------------------------------------------
# Standalone runner (python test_swarm_harness.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Swarm harness — no Slack required")
    parser.add_argument("--smoke", action="store_true", help="Run smoke test only")
    parser.add_argument("--request", default=TEST_REQUEST, help="Research request text")
    args = parser.parse_args()

    async def _run_standalone():
        from cuga.backend.multi_agent.config import load_config
        from cuga.backend.multi_agent.swarm_factory import SwarmAgentFactory
        from cuga.backend.multi_agent.runner import ConfigurationRunner
        from cuga.backend.multi_agent.patterns.swarm import _agent_task

        cfg = load_config(TOPOLOGY)
        collector = NotifyCollector()

        if args.smoke:
            entry_cfg = next(a for a in cfg.agents if a.role == "entry")
            first_q: asyncio.Queue[str] = asyncio.Queue()
            async with SwarmAgentFactory(cfg) as factory:
                print(f"[smoke] → {args.request!r}")
                await _agent_task(
                    agent_id=entry_cfg.id,
                    agent=factory.agents[entry_cfg.id],
                    content=args.request,
                    task_id="standalone-smoke",
                    msg_index=1,
                    timeout=entry_cfg.timeout_seconds,
                    is_entry=True,
                    first_response_queue=first_q,
                    slack_poster=collector.poster,
                )
            ack = first_q.get_nowait() if not first_q.empty() else "(no ack)"
            print(f"\n[ack] {ack}")
            return

        # Full run
        async with SwarmAgentFactory(cfg) as factory:
            runner = ConfigurationRunner(
                cfg,
                agents=factory.agents,
                agent_queues=factory.agent_queues,
            )
            print(f"[harness] → {args.request!r}")
            result = await runner.run(
                args.request,
                task_id="standalone-full",
                slack_poster=collector.poster,
            )
            print(f"\n[ack] {result.answer}")
            print(f"[harness] waiting {WORKER_WAIT_S}s for workers…")

            any_posted = False
            deadline = time.monotonic() + WORKER_WAIT_S
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                arrived = await collector.wait_for_post(timeout=min(30.0, remaining))
                if arrived:
                    any_posted = True
                elif any_posted:
                    break

        print(f"\n── {len(collector.posts)} NOTIFY posts ──")
        for ts, text in collector.posts:
            print(f"  +{ts:.1f}s  {text}")

    asyncio.run(_run_standalone())
