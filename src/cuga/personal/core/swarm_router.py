"""SwarmRouter — config-driven, multi-topology swarm routing for the personal layer.

Scans one or more directories for ``SWARM.md + topology.toml`` pairs at startup.
Each swarm declares its trigger phrases in ``SWARM.md`` frontmatter (same YAML
convention as ``SKILL.md``).  Incoming messages are matched against all loaded
swarms; the first match wins.

Directory layout::

    skills/swarms/
        chief-of-staff-research/
            SWARM.md        ← triggers declared here
            topology.toml   ← swarm wiring
        sanity-check/
            SWARM.md
            topology.toml

Usage in ``PersonalAgentOrchestrator``::

    from cuga.personal.core.swarm_router import SwarmRouter

    # At startup (in cli/main.py _run()):
    router = SwarmRouter.from_dirs(["./skills/swarms", "~/.cuga/swarms"], gateway=adapter)

    # Per message (step 0 in orchestrator.handle_message):
    if await router.try_handle(event, target):
        return

Adding a new swarm: drop a folder with SWARM.md + topology.toml into the swarms
directory and restart — no code changes required.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import yaml
from loguru import logger

if TYPE_CHECKING:
    from cuga.personal.gateway.base import DeliveryTarget, MessageEvent


# ---------------------------------------------------------------------------
# SWARM.md parsing
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str):
    """Return (frontmatter_str, body_str) from a Markdown file with YAML front matter."""
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].strip()


@dataclass
class SwarmMetadata:
    name: str
    description: str
    topology_file: str          # relative path from the swarm dir
    trigger_groups: List[List[str]]  # list of keyword groups; any group matching = trigger

    @classmethod
    def from_markdown(cls, text: str) -> "SwarmMetadata":
        frontmatter, _ = _split_frontmatter(text)
        data = yaml.safe_load(frontmatter) or {}

        trigger_groups: List[List[str]] = []
        for trigger in data.get("triggers", []):
            if trigger.get("type") == "keyword":
                values = trigger.get("value", [])
                op = trigger.get("operator", "or")
                if op == "or" and values:
                    # Each keyword is its own group (any one matches)
                    trigger_groups.append([v.lower() for v in values])
                elif op == "and" and values:
                    # All keywords must match — treat as a single AND-group
                    trigger_groups.append([v.lower() for v in values])

        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            topology_file=data.get("topology", "topology.toml"),
            trigger_groups=trigger_groups,
        )

    def matches(self, text: str) -> bool:
        """Return True if text triggers this swarm."""
        t = text.lower()
        for group in self.trigger_groups:
            if any(kw in t for kw in group):
                return True
        return False


# ---------------------------------------------------------------------------
# Per-swarm runner entry (lazy-initialised)
# ---------------------------------------------------------------------------

@dataclass
class _SwarmEntry:
    name: str
    topology_path: Path
    metadata: SwarmMetadata
    gateway: object             # set after adapter is created; may be updated later
    _runner: object = field(default=None, repr=False)
    _factory: object = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def ensure_runner(self) -> None:
        """Build the ConfigurationRunner on first use (thread-safe)."""
        async with self._lock:
            if self._runner is not None:
                return

            from cuga.backend.multi_agent.config import load_config
            from cuga.backend.multi_agent.swarm_factory import SwarmAgentFactory
            from cuga.backend.multi_agent.runner import ConfigurationRunner

            cfg = load_config(self.topology_path)
            logger.info(
                f"[SwarmRouter:{self.name}] loading topology '{cfg.name}' "
                f"({cfg.pattern}, {len(cfg.agents)} agents)"
            )
            factory = SwarmAgentFactory(cfg)
            await factory.__aenter__()
            self._factory = factory

            self._runner = ConfigurationRunner(
                cfg,
                agents=factory.agents,
                agent_queues=factory.agent_queues,
            )
            logger.info(f"[SwarmRouter:{self.name}] runner ready")

    async def run(self, event: "MessageEvent", target: "DeliveryTarget") -> None:
        """Fire the swarm and route results back via the gateway."""
        task_id = str(uuid.uuid4())[:8]
        gateway = self.gateway

        async def slack_poster(text: str) -> None:
            try:
                await gateway.send(target, text)
            except Exception as exc:
                logger.warning(f"[SwarmRouter:{self.name}] slack_poster error: {exc}")

        try:
            result = await self._runner.run(
                request=event.text,
                task_id=task_id,
                slack_poster=slack_poster,
            )
            if result and result.answer:
                await slack_poster(result.answer)
        except Exception as exc:
            logger.error(f"[SwarmRouter:{self.name}] swarm error: {exc}")
            await slack_poster(f"❌ Swarm error ({self.name}): {exc}")


# ---------------------------------------------------------------------------
# SwarmRouter — the public API
# ---------------------------------------------------------------------------

class SwarmRouter:
    """Config-driven router for multi-agent swarms.

    Scans one or more directories for ``SWARM.md + topology.toml`` pairs.
    Each swarm's trigger phrases come from its ``SWARM.md`` frontmatter.

    Gateway is injected after construction (so it can be set once the Slack
    adapter is live), or passed directly to ``from_dirs``.
    """

    def __init__(self, entries: List[_SwarmEntry]) -> None:
        self._entries = entries

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_dirs(
        cls,
        dirs: List[str | Path],
        gateway=None,
    ) -> "SwarmRouter":
        """Scan directories for SWARM.md+topology.toml pairs and build a router."""
        entries: List[_SwarmEntry] = []

        for base in dirs:
            base = Path(base).expanduser().resolve()
            if not base.exists():
                logger.debug(f"[SwarmRouter] swarm dir not found, skipping: {base}")
                continue
            for candidate in sorted(base.iterdir()):
                if not candidate.is_dir():
                    continue
                swarm_md = candidate / "SWARM.md"
                if not swarm_md.exists():
                    continue
                try:
                    meta = SwarmMetadata.from_markdown(swarm_md.read_text())
                    topology_path = candidate / meta.topology_file
                    if not topology_path.exists():
                        logger.warning(
                            f"[SwarmRouter] topology not found for '{meta.name}': {topology_path}"
                        )
                        continue
                    entries.append(
                        _SwarmEntry(
                            name=meta.name,
                            topology_path=topology_path,
                            metadata=meta,
                            gateway=gateway,
                        )
                    )
                    trigger_count = sum(len(g) for g in meta.trigger_groups)
                    logger.info(
                        f"[SwarmRouter] registered '{meta.name}' "
                        f"({trigger_count} trigger keywords)"
                    )
                except Exception as exc:
                    logger.warning(
                        f"[SwarmRouter] failed to load swarm at {candidate}: {exc}"
                    )

        if not entries:
            logger.info("[SwarmRouter] no swarms found — multi-agent routing disabled")
        return cls(entries)

    # ------------------------------------------------------------------
    # Gateway injection (called after the Slack adapter is constructed)
    # ------------------------------------------------------------------

    @property
    def gateway(self):
        return self._entries[0].gateway if self._entries else None

    @gateway.setter
    def gateway(self, value) -> None:
        for entry in self._entries:
            entry.gateway = value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def try_handle(
        self, event: "MessageEvent", target: "DeliveryTarget"
    ) -> bool:
        """Return True and delegate to the matching swarm if triggered."""
        for entry in self._entries:
            if entry.metadata.matches(event.text):
                logger.info(
                    f"[SwarmRouter] '{entry.name}' triggered by: {event.text[:60]!r}"
                )
                await entry.ensure_runner()
                asyncio.create_task(entry.run(event, target))
                return True
        return False

    def registered_swarms(self) -> List[str]:
        return [e.name for e in self._entries]
