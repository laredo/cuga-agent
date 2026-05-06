"""SkillLoader — scans directories and loads skill bundles from disk."""
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from cuga.personal.skills.models import LoadedSkill, SkillMetadata, _split_frontmatter


class SkillLoader:
    """
    Loads skills from one or more filesystem directories.

    A skill directory must contain a SKILL.md file with YAML frontmatter.
    Optional: mcp_servers.yaml, policies/*.md, knowledge/*.md
    """

    def __init__(self, skill_dirs: List[str]):
        self._dirs = [Path(d).expanduser() for d in skill_dirs]
        self._index: Dict[str, Path] = {}  # name → skill directory path

    async def scan(self) -> List[SkillMetadata]:
        """Scan all skill dirs, return list of SkillMetadata for valid skills."""
        self._index.clear()
        found: List[SkillMetadata] = []
        for base_dir in self._dirs:
            if not base_dir.exists():
                continue
            for candidate in base_dir.iterdir():
                if not candidate.is_dir():
                    continue
                skill_md = candidate / "SKILL.md"
                if not skill_md.exists():
                    continue
                try:
                    meta = SkillMetadata.from_markdown(skill_md.read_text())
                    self._index[meta.name] = candidate
                    found.append(meta)
                except Exception:
                    pass  # skip malformed skill dirs
        return found

    async def load(self, skill_name: str) -> LoadedSkill:
        """Fully load a skill by name. Raises KeyError if not found."""
        if skill_name not in self._index:
            raise KeyError(f"Skill '{skill_name}' not found. Did you call scan() first?")

        path = self._index[skill_name]
        meta = SkillMetadata.from_markdown((path / "SKILL.md").read_text())

        policies = _load_policies(path / "policies")
        tool_config = _load_yaml(path / "mcp_servers.yaml")
        knowledge = _load_knowledge(path / "knowledge")

        return LoadedSkill(
            metadata=meta,
            path=str(path),
            policies=policies,
            tool_config=tool_config,
            knowledge=knowledge,
        )

    async def activate(self, skill: LoadedSkill, agent) -> None:
        """
        Activate a loaded skill on a CugaAgent:
        1. Load skill policies into agent.policies using the typed async API
        2. Inject knowledge docs into agent context
        """
        policies_manager = getattr(agent, "policies", None)
        if policies_manager is not None:
            for policy in skill.policies:
                await _add_policy(policies_manager, policy)

        # Inject knowledge (best-effort — agent may not support this yet)
        if skill.knowledge:
            knowledge_text = "\n\n".join(skill.knowledge)
            context = getattr(agent, "context", None)
            if context is not None and hasattr(context, "append"):
                context.append({"role": "system", "content": knowledge_text})

    def get_skill_path(self, skill_name: str) -> Optional[Path]:
        return self._index.get(skill_name)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

async def _add_policy(policies_manager, policy: dict) -> None:
    """Map a parsed policy dict to the correct CugaAgent async API call."""
    policy_type = policy.get("type", "")
    name = policy.get("name", "skill-policy")
    body = policy.get("_body", "")
    description = policy.get("description", "")

    # Extract keyword list from triggers (first keyword trigger wins)
    keywords: list = []
    for trigger in policy.get("triggers", []):
        if trigger.get("type") == "keyword":
            keywords = trigger.get("value", [])
            break

    try:
        if policy_type == "playbook":
            if not keywords:
                keywords = [name]
            await policies_manager.add_playbook(
                name=name,
                content=body,
                keywords=keywords,
                description=description,
            )
        elif policy_type == "tool_approval":
            required_tools: list = []
            for trigger in policy.get("triggers", []):
                if trigger.get("type") == "tool_name":
                    required_tools = trigger.get("value", [])
                    break
            if required_tools:
                await policies_manager.add_tool_approval(
                    name=name,
                    required_tools=required_tools,
                    description=description,
                    approval_message=body.strip() or None,
                )
        elif policy_type == "intent_guard":
            if keywords:
                await policies_manager.add_intent_guard(
                    name=name,
                    keywords=keywords,
                    description=description,
                )
        # Unknown types are silently skipped
    except Exception:
        pass  # best-effort — don't crash the message loop


def _load_policies(policies_dir: Path) -> List[dict]:
    """Parse all .md files in the policies/ directory as policy dicts."""
    if not policies_dir.exists():
        return []
    results = []
    for md_file in sorted(policies_dir.glob("*.md")):
        try:
            content = md_file.read_text()
            frontmatter, body = _split_frontmatter(content)
            data = yaml.safe_load(frontmatter) or {}
            data["_body"] = body
            results.append(data)
        except Exception:
            pass
    return results


def _load_yaml(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text())
    except Exception:
        return None


def _load_knowledge(knowledge_dir: Path) -> List[str]:
    if not knowledge_dir.exists():
        return []
    texts = []
    for md_file in sorted(knowledge_dir.glob("*.md")):
        try:
            texts.append(md_file.read_text())
        except Exception:
            pass
    return texts
