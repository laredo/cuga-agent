"""Tests for SkillLoader — filesystem scanning and loading."""
import textwrap
import pytest

from cuga.personal.skills.loader import SkillLoader
from cuga.personal.skills.models import LoadedSkill


SKILL_MD = textwrap.dedent("""\
    ---
    name: test-skill
    description: "A test skill"
    version: "1.0.0"
    commands: ["/test"]
    triggers:
      - type: keyword
        value: ["test", "testing"]
    ---
    # Test Skill
    Does testing things.
""")

MCP_YAML = textwrap.dedent("""\
    mcpServers:
      test_server:
        url: http://localhost:9000/sse
        transport: sse
        description: "Test MCP server"
""")

PLAYBOOK_MD = textwrap.dedent("""\
    ---
    type: playbook
    name: test-playbook
    triggers:
      - type: keyword
        value: ["test"]
    ---
    ## Steps
    1. Do thing A
    2. Do thing B
""")

KNOWLEDGE_MD = "This is domain knowledge for the test skill."


@pytest.fixture
def skill_dir(tmp_path):
    """Create a minimal skill directory on disk."""
    skill = tmp_path / "test-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(SKILL_MD)
    policies_dir = skill / "policies"
    policies_dir.mkdir()
    (policies_dir / "playbook.md").write_text(PLAYBOOK_MD)
    knowledge_dir = skill / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "notes.md").write_text(KNOWLEDGE_MD)
    (skill / "mcp_servers.yaml").write_text(MCP_YAML)
    return tmp_path


class TestSkillLoader:
    @pytest.mark.asyncio
    async def test_scan_finds_skill(self, skill_dir):
        loader = SkillLoader([str(skill_dir)])
        skills = await loader.scan()
        assert len(skills) == 1
        assert skills[0].name == "test-skill"

    @pytest.mark.asyncio
    async def test_load_returns_loaded_skill(self, skill_dir):
        loader = SkillLoader([str(skill_dir)])
        await loader.scan()
        skill = await loader.load("test-skill")
        assert isinstance(skill, LoadedSkill)
        assert skill.metadata.name == "test-skill"
        assert skill.metadata.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_load_reads_policies(self, skill_dir):
        loader = SkillLoader([str(skill_dir)])
        await loader.scan()
        skill = await loader.load("test-skill")
        assert len(skill.policies) == 1
        assert skill.policies[0]["name"] == "test-playbook"

    @pytest.mark.asyncio
    async def test_load_reads_tool_config(self, skill_dir):
        loader = SkillLoader([str(skill_dir)])
        await loader.scan()
        skill = await loader.load("test-skill")
        assert skill.tool_config is not None
        assert "mcpServers" in skill.tool_config

    @pytest.mark.asyncio
    async def test_load_reads_knowledge(self, skill_dir):
        loader = SkillLoader([str(skill_dir)])
        await loader.scan()
        skill = await loader.load("test-skill")
        assert len(skill.knowledge) == 1
        assert "domain knowledge" in skill.knowledge[0]

    @pytest.mark.asyncio
    async def test_load_unknown_skill_raises(self, skill_dir):
        loader = SkillLoader([str(skill_dir)])
        await loader.scan()
        with pytest.raises(KeyError):
            await loader.load("no-such-skill")

    @pytest.mark.asyncio
    async def test_scan_skips_directories_without_skill_md(self, tmp_path):
        (tmp_path / "not-a-skill").mkdir()
        loader = SkillLoader([str(tmp_path)])
        skills = await loader.scan()
        assert skills == []

    @pytest.mark.asyncio
    async def test_scan_multiple_dirs(self, skill_dir, tmp_path):
        """Skills from multiple scan dirs are merged."""
        other_dir = tmp_path / "other-skills"
        other_dir.mkdir()
        other_skill = other_dir / "other-skill"
        other_skill.mkdir()
        (other_skill / "SKILL.md").write_text(
            "---\nname: other-skill\ndescription: Another skill\n---\n"
        )
        loader = SkillLoader([str(skill_dir), str(other_dir)])
        skills = await loader.scan()
        names = [s.name for s in skills]
        assert "test-skill" in names
        assert "other-skill" in names
