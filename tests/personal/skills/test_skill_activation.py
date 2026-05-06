"""Tests for skill activation — loading policies and tools into a CugaAgent."""
import textwrap
import pytest
from unittest.mock import AsyncMock, MagicMock

from cuga.personal.skills.loader import SkillLoader


SKILL_MD = textwrap.dedent("""\
    ---
    name: activate-test-skill
    description: "Skill for testing activation"
    commands: ["/activate-test"]
    ---
    # Activate Test Skill
""")

PLAYBOOK_MD = textwrap.dedent("""\
    ---
    type: playbook
    name: activate-test-playbook
    triggers:
      - type: keyword
        value: ["activate"]
    ---
    ## Steps
    1. Do the thing
""")


@pytest.fixture
def skill_dir(tmp_path):
    skill = tmp_path / "activate-test-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(SKILL_MD)
    policies_dir = skill / "policies"
    policies_dir.mkdir()
    (policies_dir / "playbook.md").write_text(PLAYBOOK_MD)
    return tmp_path


class TestSkillActivation:
    @pytest.mark.asyncio
    async def test_activate_loads_policies(self, skill_dir):
        """activate() should inject skill policies into the agent."""
        loader = SkillLoader([str(skill_dir)])
        await loader.scan()
        skill = await loader.load("activate-test-skill")

        mock_policies = MagicMock()
        mock_policies.add_playbook = AsyncMock(return_value="policy-id-1")
        mock_agent = MagicMock()
        mock_agent.policies = mock_policies

        await loader.activate(skill, mock_agent)

        mock_policies.add_playbook.assert_called_once()
        call_kwargs = mock_policies.add_playbook.call_args.kwargs
        assert call_kwargs["name"] == "activate-test-playbook"
        assert "Do the thing" in call_kwargs["content"]
        assert "activate" in call_kwargs["keywords"]

    @pytest.mark.asyncio
    async def test_activate_with_no_policies(self, tmp_path):
        """activate() works fine when skill has no policies."""
        skill = tmp_path / "bare-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: bare-skill\ndescription: bare\n---\n")

        loader = SkillLoader([str(tmp_path)])
        await loader.scan()
        loaded = await loader.load("bare-skill")

        mock_policies = MagicMock()
        mock_policies.add_playbook = AsyncMock()
        mock_agent = MagicMock()
        mock_agent.policies = mock_policies
        await loader.activate(loaded, mock_agent)  # should not raise

    @pytest.mark.asyncio
    async def test_activate_injects_knowledge_as_context(self, tmp_path):
        """activate() injects knowledge files into the agent context."""
        skill = tmp_path / "knowledge-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: knowledge-skill\ndescription: with knowledge\n---\n")
        knowledge_dir = skill / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "notes.md").write_text("Important domain knowledge here.")

        loader = SkillLoader([str(tmp_path)])
        await loader.scan()
        loaded = await loader.load("knowledge-skill")
        assert len(loaded.knowledge) == 1
