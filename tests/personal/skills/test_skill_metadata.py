"""Tests for SkillMetadata parsing from SKILL.md frontmatter."""
import textwrap
import pytest

from cuga.personal.skills.models import SkillMetadata, LoadedSkill


MINIMAL_FRONTMATTER = textwrap.dedent("""\
    ---
    name: my-skill
    description: "Does something"
    ---
    # My Skill
    Body text here.
""")

FULL_FRONTMATTER = textwrap.dedent("""\
    ---
    name: fill-timesheet
    description: "Automatically fill weekly timesheet"
    version: "1.0.0"
    author: "employee@company.com"
    platforms: [slack, cli]
    requires_tools: [jira, calendar]
    commands: ["/timesheet"]
    triggers:
      - type: keyword
        value: ["timesheet", "time sheet"]
        operator: or
    schedule_hint: "0 16 * * 5"
    enterprise:
      category: hr
      approval_required: false
    ---
    # Fill Timesheet
    Body text.
""")


class TestSkillMetadata:
    def test_minimal_direct_creation(self):
        meta = SkillMetadata(name="my-skill", description="Does something")
        assert meta.name == "my-skill"
        assert meta.version == "0.1.0"
        assert meta.platforms == []
        assert meta.commands == []
        assert meta.schedule_hint is None

    def test_full_direct_creation(self):
        meta = SkillMetadata(
            name="fill-timesheet",
            description="Fills timesheet",
            version="1.0.0",
            author="me@example.com",
            platforms=["slack", "cli"],
            requires_tools=["jira"],
            commands=["/timesheet"],
            triggers=[{"type": "keyword", "value": ["timesheet"], "operator": "or"}],
            schedule_hint="0 16 * * 5",
            enterprise={"category": "hr"},
        )
        assert meta.author == "me@example.com"
        assert "slack" in meta.platforms
        assert "/timesheet" in meta.commands
        assert meta.schedule_hint == "0 16 * * 5"
        assert meta.enterprise["category"] == "hr"

    def test_parse_from_minimal_markdown(self):
        meta = SkillMetadata.from_markdown(MINIMAL_FRONTMATTER)
        assert meta.name == "my-skill"
        assert meta.description == "Does something"

    def test_parse_from_full_markdown(self):
        meta = SkillMetadata.from_markdown(FULL_FRONTMATTER)
        assert meta.name == "fill-timesheet"
        assert meta.version == "1.0.0"
        assert "slack" in meta.platforms
        assert "/timesheet" in meta.commands
        assert len(meta.triggers) == 1
        assert meta.schedule_hint == "0 16 * * 5"
        assert meta.enterprise["category"] == "hr"

    def test_parse_raises_on_missing_name(self):
        bad = "---\ndescription: no name\n---\n"
        with pytest.raises((ValueError, KeyError)):
            SkillMetadata.from_markdown(bad)

    def test_parse_raises_on_missing_description(self):
        bad = "---\nname: no-desc\n---\n"
        with pytest.raises((ValueError, KeyError)):
            SkillMetadata.from_markdown(bad)


class TestLoadedSkill:
    def test_creation(self):
        meta = SkillMetadata(name="calc", description="A calculator skill")
        skill = LoadedSkill(metadata=meta, path="/skills/calc")
        assert skill.metadata.name == "calc"
        assert skill.path == "/skills/calc"
        assert skill.policies == []
        assert skill.tool_config is None
        assert skill.knowledge == []
