"""TOML-driven multi-agent topology configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Leaf models
# ---------------------------------------------------------------------------

class ModelConfig(BaseModel):
    provider: Literal["openai", "watsonx", "azure", "groq", "openrouter"]
    name: str
    temperature: Optional[float] = None

    @field_validator("temperature")
    @classmethod
    def _check_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v


class SkillsConfig(BaseModel):
    enabled: bool = False
    paths: List[str] = []
    allowed: List[str] = []


class PolicyConfig(BaseModel):
    type: Literal["tool_approval", "intent_guard", "output_formatter", "playbook", "tool_guide"]
    name: str
    description: Optional[str] = None
    format: Optional[str] = None
    required_tools: Optional[List[str]] = None

    @model_validator(mode="after")
    def _tool_approval_needs_tools(self) -> "PolicyConfig":
        if self.type == "tool_approval" and not self.required_tools:
            raise ValueError("tool_approval policy requires required_tools")
        return self


class MCPServerConfig(BaseModel):
    name: str
    url: str


class ToolConfig(BaseModel):
    name: str
    module: str
    func: str


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AgentConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    type: Literal["cuga_lite", "cuga_supervisor", "external"]
    domain: Optional[str] = None
    role: Literal["entry", "worker", "exit"]
    instructions: Optional[str] = None
    enable_knowledge: Optional[bool] = None
    max_steps: int = 20
    timeout_seconds: int = 120
    model: Optional[ModelConfig] = None
    apps: List[str] = []
    mcp_servers: List[MCPServerConfig] = []
    tools: List[ToolConfig] = []
    skills: Optional[SkillsConfig] = None
    policies: List[PolicyConfig] = []
    peers: List[str] = []
    a2a_protocol: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

class EdgeConfig(BaseModel):
    # `from` is a Python keyword — use alias
    from_agent: str = Field(alias="from")
    to: str
    mode: Literal["one_way", "peer_to_peer", "supervisor"]

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _no_self_loop(self) -> "EdgeConfig":
        if self.from_agent == self.to:
            raise ValueError("Self-loops are not allowed in edge definitions")
        return self


# ---------------------------------------------------------------------------
# Sub-configuration (nested topology block)
# ---------------------------------------------------------------------------

class SubConfigurationConfig(BaseModel):
    name: str
    agents: List[str]
    edges: List[EdgeConfig] = []


# ---------------------------------------------------------------------------
# Top-level configuration
# ---------------------------------------------------------------------------

_PATTERNS_REQUIRING_EXIT = {"pipeline", "peer_to_peer", "hybrid"}


class MultiAgentConfig(BaseModel):
    name: str
    pattern: Literal["pipeline", "supervisor", "peer_to_peer", "hybrid", "swarm"]
    agents: List[AgentConfig]
    edges: List[EdgeConfig] = []
    sub_configurations: List[SubConfigurationConfig] = []

    @model_validator(mode="after")
    def _validate_topology(self) -> "MultiAgentConfig":
        agents = self.agents
        agent_ids = [a.id for a in agents]

        if len(agents) < 2:
            raise ValueError("Configuration requires at least 2 agents")
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Duplicate agent IDs are not allowed")

        entries = [a for a in agents if a.role == "entry"]
        if len(entries) != 1:
            raise ValueError("Exactly one entry agent is required")

        if self.pattern in _PATTERNS_REQUIRING_EXIT:
            exits = [a for a in agents if a.role == "exit"]
            if len(exits) != 1:
                raise ValueError("Exactly one exit agent is required")

        known = set(agent_ids)
        for edge in self.edges:
            if edge.from_agent not in known or edge.to not in known:
                raise ValueError(
                    f"Edge references unknown agent: {edge.from_agent!r} → {edge.to!r}"
                )

        return self


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: str | Path) -> MultiAgentConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    cfg = dict(raw.get("configuration", {}))
    cfg["agents"] = raw.get("agents", [])
    cfg["edges"] = raw.get("edges", [])
    cfg["sub_configurations"] = raw.get("sub_configurations", [])

    return MultiAgentConfig(**cfg)
