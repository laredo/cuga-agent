"""
Unit tests for multi-agent TOML configuration parsing and validation.

Tests cover:
- All agent property types (identity, model, skills, tools, policies, peers)
- Topology patterns (pipeline, supervisor, peer_to_peer, hybrid)
- Edge validation and sub-configurations
- Invalid / missing required fields
- Default value inheritance
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from cuga.backend.multi_agent.config import (
    AgentConfig,
    EdgeConfig,
    ModelConfig,
    SkillsConfig,
    PolicyConfig,
    MCPServerConfig,
    ToolConfig,
    SubConfigurationConfig,
    MultiAgentConfig,
    load_config,
)

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "multi_agent"


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------

class TestAgentConfig:

    def test_minimal_agent(self):
        agent = AgentConfig(id="planner", type="cuga_lite", domain="planning", role="entry")
        assert agent.id == "planner"
        assert agent.type == "cuga_lite"
        assert agent.domain == "planning"
        assert agent.role == "entry"

    def test_defaults(self):
        agent = AgentConfig(id="a", type="cuga_lite", domain="d", role="worker")
        assert agent.model is None
        assert agent.instructions is None
        assert agent.enable_knowledge is None
        assert agent.max_steps == 20
        assert agent.timeout_seconds == 120
        assert agent.apps == []
        assert agent.mcp_servers == []
        assert agent.tools == []
        assert agent.skills is None
        assert agent.policies == []
        assert agent.peers == []
        assert agent.a2a_protocol is None

    def test_valid_roles(self):
        for role in ("entry", "worker", "exit"):
            a = AgentConfig(id="x", type="cuga_lite", domain="d", role=role)
            assert a.role == role

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            AgentConfig(id="x", type="cuga_lite", domain="d", role="invalid_role")

    def test_valid_types(self):
        for t in ("cuga_lite", "cuga_supervisor", "external"):
            a = AgentConfig(id="x", type=t, domain="d", role="worker")
            assert a.type == t

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            AgentConfig(id="x", type="unknown_type", domain="d", role="worker")

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            AgentConfig(type="cuga_lite", domain="d", role="worker")  # no id

    def test_full_agent(self):
        agent = AgentConfig(
            id="researcher",
            type="cuga_lite",
            domain="research",
            role="worker",
            instructions="You research things.",
            enable_knowledge=True,
            max_steps=15,
            timeout_seconds=90,
            apps=["web_search", "crm"],
            peers=["fact_checker"],
            model=ModelConfig(provider="openai", name="gpt-4o", temperature=0.1),
            skills=SkillsConfig(enabled=True, allowed=["web_research"]),
            policies=[PolicyConfig(type="intent_guard", name="No spam", description="Block spam")],
            mcp_servers=[MCPServerConfig(name="fs", url="http://localhost:8001/mcp/fs")],
            tools=[ToolConfig(name="summarize", module="myproject.tools", func="summarize")],
        )
        assert agent.apps == ["web_search", "crm"]
        assert agent.peers == ["fact_checker"]
        assert agent.model.name == "gpt-4o"
        assert agent.skills.enabled is True
        assert len(agent.policies) == 1
        assert len(agent.mcp_servers) == 1
        assert len(agent.tools) == 1

    def test_external_agent_requires_a2a(self):
        """External agents should have a2a_protocol configured."""
        agent = AgentConfig(
            id="ext",
            type="external",
            domain="external",
            role="worker",
            a2a_protocol={"enabled": True, "endpoint": "https://ext.example.com/a2a"},
        )
        assert agent.a2a_protocol["enabled"] is True


# ---------------------------------------------------------------------------
# ModelConfig
# ---------------------------------------------------------------------------

class TestModelConfig:

    def test_valid_providers(self):
        for provider in ("openai", "watsonx", "azure", "groq", "openrouter"):
            m = ModelConfig(provider=provider, name="model-x")
            assert m.provider == provider

    def test_invalid_provider_raises(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="unknown_llm", name="model-x")

    def test_temperature_defaults_to_none(self):
        m = ModelConfig(provider="openai", name="gpt-4o")
        assert m.temperature is None

    def test_temperature_range(self):
        ModelConfig(provider="openai", name="gpt-4o", temperature=0.0)
        ModelConfig(provider="openai", name="gpt-4o", temperature=2.0)

    def test_temperature_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            ModelConfig(provider="openai", name="gpt-4o", temperature=2.1)
        with pytest.raises(ValidationError):
            ModelConfig(provider="openai", name="gpt-4o", temperature=-0.1)


# ---------------------------------------------------------------------------
# SkillsConfig
# ---------------------------------------------------------------------------

class TestSkillsConfig:

    def test_defaults(self):
        s = SkillsConfig()
        assert s.enabled is False
        assert s.paths == []
        assert s.allowed == []

    def test_all_skills_when_allowed_empty(self):
        s = SkillsConfig(enabled=True)
        assert s.allowed == []  # empty = all discovered skills

    def test_restricted_skills(self):
        s = SkillsConfig(enabled=True, allowed=["web_research", "doc_summarizer"])
        assert "web_research" in s.allowed

    def test_custom_paths(self):
        s = SkillsConfig(enabled=True, paths=[".agents/skills/research/"])
        assert len(s.paths) == 1


# ---------------------------------------------------------------------------
# PolicyConfig
# ---------------------------------------------------------------------------

class TestPolicyConfig:

    def test_valid_policy_types(self):
        for t in ("tool_approval", "intent_guard", "output_formatter", "playbook", "tool_guide"):
            kwargs = {"type": t, "name": "test policy"}
            if t == "tool_approval":
                kwargs["required_tools"] = ["some_tool"]
            p = PolicyConfig(**kwargs)
            assert p.type == t

    def test_invalid_policy_type_raises(self):
        with pytest.raises(ValidationError):
            PolicyConfig(type="unknown_policy", name="test")

    def test_tool_approval_requires_required_tools(self):
        with pytest.raises(ValidationError):
            PolicyConfig(type="tool_approval", name="test")  # missing required_tools

    def test_tool_approval_valid(self):
        p = PolicyConfig(type="tool_approval", name="test", required_tools=["db_delete"])
        assert p.required_tools == ["db_delete"]


# ---------------------------------------------------------------------------
# EdgeConfig
# ---------------------------------------------------------------------------

class TestEdgeConfig:

    def test_one_way_edge(self):
        e = EdgeConfig(from_agent="planner", to="researcher", mode="one_way")
        assert e.from_agent == "planner"
        assert e.to == "researcher"
        assert e.mode == "one_way"

    def test_peer_to_peer_edge(self):
        e = EdgeConfig(from_agent="a", to="b", mode="peer_to_peer")
        assert e.mode == "peer_to_peer"

    def test_supervisor_edge(self):
        e = EdgeConfig(from_agent="supervisor", to="worker", mode="supervisor")
        assert e.mode == "supervisor"

    def test_invalid_mode_raises(self):
        with pytest.raises(ValidationError):
            EdgeConfig(from_agent="a", to="b", mode="invalid_mode")

    def test_self_loop_raises(self):
        with pytest.raises(ValidationError):
            EdgeConfig(from_agent="a", to="a", mode="one_way")


# ---------------------------------------------------------------------------
# MultiAgentConfig (full topology)
# ---------------------------------------------------------------------------

class TestMultiAgentConfig:

    def _make_config(self, pattern="pipeline", agents=None, edges=None):
        agents = agents or [
            AgentConfig(id="a", type="cuga_lite", domain="d", role="entry"),
            AgentConfig(id="b", type="cuga_lite", domain="d", role="exit"),
        ]
        edges = edges or [EdgeConfig(from_agent="a", to="b", mode="one_way")]
        return MultiAgentConfig(
            name=f"test_{pattern}",
            pattern=pattern,
            agents=agents,
            edges=edges,
        )

    def test_valid_patterns(self):
        for pattern in ("pipeline", "supervisor", "peer_to_peer", "hybrid"):
            cfg = self._make_config(pattern=pattern)
            assert cfg.pattern == pattern

    def test_invalid_pattern_raises(self):
        with pytest.raises(ValidationError):
            self._make_config(pattern="unknown")

    def test_requires_at_least_two_agents(self):
        with pytest.raises(ValidationError):
            self._make_config(agents=[
                AgentConfig(id="only", type="cuga_lite", domain="d", role="entry")
            ])

    def test_requires_exactly_one_entry_agent(self):
        with pytest.raises(ValidationError):
            self._make_config(agents=[
                AgentConfig(id="a", type="cuga_lite", domain="d", role="entry"),
                AgentConfig(id="b", type="cuga_lite", domain="d", role="entry"),
            ])

    def test_requires_exactly_one_exit_agent(self):
        with pytest.raises(ValidationError):
            self._make_config(agents=[
                AgentConfig(id="a", type="cuga_lite", domain="d", role="entry"),
                AgentConfig(id="b", type="cuga_lite", domain="d", role="exit"),
                AgentConfig(id="c", type="cuga_lite", domain="d", role="exit"),
            ])

    def test_duplicate_agent_ids_raise(self):
        with pytest.raises(ValidationError):
            self._make_config(agents=[
                AgentConfig(id="dup", type="cuga_lite", domain="d", role="entry"),
                AgentConfig(id="dup", type="cuga_lite", domain="d", role="exit"),
            ])

    def test_edge_referencing_unknown_agent_raises(self):
        with pytest.raises(ValidationError):
            self._make_config(edges=[
                EdgeConfig(from_agent="a", to="nonexistent", mode="one_way")
            ])

    def test_large_agent_count_is_allowed(self):
        """No hard upper limit on the number of agents."""
        agents = [
            AgentConfig(id=f"agent_{i}", type="cuga_lite", domain="d", role="worker")
            for i in range(20)
        ]
        agents[0] = AgentConfig(id="agent_0", type="cuga_lite", domain="d", role="entry")
        agents[-1] = AgentConfig(id=f"agent_{len(agents)-1}", type="cuga_lite", domain="d", role="exit")
        cfg = MultiAgentConfig(name="large", pattern="pipeline", agents=agents, edges=[])
        assert len(cfg.agents) == 20

    def test_sub_configurations(self):
        cfg = self._make_config()
        cfg.sub_configurations = [
            SubConfigurationConfig(
                name="verify",
                agents=["a", "b"],
                edges=[EdgeConfig(from_agent="a", to="b", mode="peer_to_peer")],
            )
        ]
        assert len(cfg.sub_configurations) == 1


# ---------------------------------------------------------------------------
# load_config (TOML → MultiAgentConfig)
# ---------------------------------------------------------------------------

class TestLoadConfig:

    def test_load_pipeline_fixture(self):
        cfg = load_config(FIXTURES / "pipeline.toml")
        assert cfg.name == "test_pipeline"
        assert cfg.pattern == "pipeline"
        assert len(cfg.agents) == 3
        assert len(cfg.edges) == 2

    def test_pipeline_agent_properties(self):
        cfg = load_config(FIXTURES / "pipeline.toml")
        researcher = next(a for a in cfg.agents if a.id == "researcher")
        assert researcher.domain == "research"
        assert researcher.model.name == "gpt-4o"
        assert researcher.skills.enabled is True
        assert "web_research" in researcher.skills.allowed
        assert len(researcher.policies) == 1

    def test_load_supervisor_fixture(self):
        cfg = load_config(FIXTURES / "supervisor.toml")
        assert cfg.pattern == "supervisor"
        supervisor = next(a for a in cfg.agents if a.type == "cuga_supervisor")
        assert supervisor.role == "entry"

    def test_load_peer_to_peer_fixture(self):
        cfg = load_config(FIXTURES / "peer_to_peer.toml")
        assert cfg.pattern == "peer_to_peer"
        researcher = next(a for a in cfg.agents if a.id == "researcher")
        assert "fact_checker" in researcher.peers

    def test_load_nested_fixture(self):
        cfg = load_config(FIXTURES / "nested.toml")
        assert len(cfg.sub_configurations) == 1
        sub = cfg.sub_configurations[0]
        assert sub.name == "verify"
        assert "researcher" in sub.agents

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config(FIXTURES / "nonexistent.toml")

    def test_invalid_toml_raises(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write("this is not valid toml ][")
            tmp = f.name
        try:
            with pytest.raises(Exception):
                load_config(tmp)
        finally:
            os.unlink(tmp)
