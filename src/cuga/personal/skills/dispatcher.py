"""SkillDispatcher — routes MessageEvents to the right skill."""

from typing import List, Optional

from cuga.personal.gateway.base import MessageEvent, MessageType
from cuga.personal.skills.models import LoadedSkill


class SkillDispatcher:
    """
    Routes a user message to the appropriate skill using:
    1. Slash command match (exact, fast)
    2. Keyword trigger match (case-insensitive substring)
    3. Natural language / semantic match (future: uses policy engine embeddings)
    """

    def __init__(self, skills: List[LoadedSkill]):
        self._skills = skills

    async def dispatch(self, event: MessageEvent) -> Optional[LoadedSkill]:
        # 1. Slash command
        if event.type == MessageType.COMMAND or event.text.startswith("/"):
            cmd = event.text.strip().split()[0].lower()
            for skill in self._skills:
                if cmd in [c.lower() for c in skill.metadata.commands]:
                    return skill

        # 2. Keyword triggers
        text_lower = event.text.lower()
        for skill in self._skills:
            for trigger in skill.metadata.triggers:
                if trigger.get("type") == "keyword":
                    values = trigger.get("value", [])
                    operator = trigger.get("operator", "or")
                    if operator == "or":
                        if any(kw.lower() in text_lower for kw in values):
                            return skill
                    elif operator == "and":
                        if all(kw.lower() in text_lower for kw in values):
                            return skill

        # 3. NL / semantic match (placeholder — Phase 2)
        return None

    def add_skill(self, skill: LoadedSkill) -> None:
        self._skills.append(skill)

    def remove_skill(self, skill_name: str) -> None:
        self._skills = [s for s in self._skills if s.metadata.name != skill_name]
