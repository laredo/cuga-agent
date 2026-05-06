"""Skill data models: SkillMetadata and LoadedSkill."""
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel


class SkillMetadata(BaseModel):
    """Parsed from a skill's SKILL.md YAML frontmatter."""

    name: str
    description: str
    version: str = "0.1.0"
    author: str = ""
    platforms: List[str] = []          # empty = all platforms
    requires_tools: List[str] = []
    commands: List[str] = []           # slash commands that trigger this skill
    triggers: List[Dict[str, Any]] = []  # policy-style triggers
    schedule_hint: Optional[str] = None
    enterprise: Dict[str, Any] = {}

    @classmethod
    def from_markdown(cls, content: str) -> "SkillMetadata":
        """
        Parse a SKILL.md string (with YAML frontmatter) and return SkillMetadata.

        Raises ValueError if required fields (name, description) are missing.
        """
        front, _ = _split_frontmatter(content)
        data = yaml.safe_load(front)
        if not data:
            raise ValueError("Empty YAML frontmatter")
        if "name" not in data:
            raise KeyError("SKILL.md frontmatter must contain 'name'")
        if "description" not in data:
            raise KeyError("SKILL.md frontmatter must contain 'description'")
        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})


class LoadedSkill(BaseModel):
    """A fully loaded skill with metadata, policies, tools, and knowledge."""

    metadata: SkillMetadata
    path: str
    policies: List[Dict[str, Any]] = []
    tool_config: Optional[Dict[str, Any]] = None
    knowledge: List[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_frontmatter(content: str):
    """Split YAML frontmatter from body. Returns (frontmatter_str, body_str)."""
    content = content.strip()
    if not content.startswith("---"):
        return "", content
    # find closing ---
    end = content.find("\n---", 3)
    if end == -1:
        return content[3:].strip(), ""
    frontmatter = content[3:end].strip()
    body = content[end + 4:].strip()
    return frontmatter, body
