"""Build live CugaAgent instances from a MultiAgentConfig.

Usage (async context manager — keeps MCP connections alive):

    async with AgentFactory(config) as factory:
        runner = ConfigurationRunner(config, agents=factory.agents)
        result = await runner.run(request, task_id="t1")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from cuga.backend.multi_agent.config import AgentConfig, MCPServerConfig, MultiAgentConfig


class AgentFactory:
    """Async context manager that builds CugaAgents and keeps MCP sessions open."""

    def __init__(self, config: "MultiAgentConfig"):
        self._config = config
        self.agents: Dict[str, Any] = {}

    async def __aenter__(self) -> "AgentFactory":
        for agent_cfg in self._config.agents:
            self.agents[agent_cfg.id] = await self._build_agent(agent_cfg)
        return self

    async def __aexit__(self, *_) -> None:
        pass

    # ------------------------------------------------------------------

    async def _build_agent(self, agent_cfg: "AgentConfig") -> Any:
        from cuga.sdk import CugaAgent

        tools = await self._load_mcp_tools(agent_cfg.mcp_servers)

        agent = CugaAgent(
            tools=tools or None,
            special_instructions=agent_cfg.instructions,
            enable_knowledge=agent_cfg.enable_knowledge,
        )

        # Scope the KB to the topology name so every agent within this
        # configuration shares one namespace and is isolated from other
        # topologies.  We pre-set _knowledge_client before the lazy property
        # fires so the auto-initialiser (which defaults to "cuga-default")
        # is never reached.
        if agent_cfg.enable_knowledge:
            self._inject_kb_scope(agent)

        return agent

    def _inject_kb_scope(self, agent: Any) -> None:
        """Pre-initialise the agent's KnowledgeClient with the topology name as scope."""
        try:
            from cuga.backend.knowledge.client import KnowledgeClient
            from cuga.backend.knowledge.engine import KnowledgeEngine
            from cuga.backend.knowledge.config import KnowledgeConfig
            from cuga.config import settings

            config = KnowledgeConfig.from_settings(settings)
            engine = KnowledgeEngine(config)
            agent._knowledge_client = KnowledgeClient(
                engine, default_agent_id=self._config.name
            )
            logger.info(
                f"KB scoped to topology '{self._config.name}' for agent"
            )
        except Exception as e:
            logger.warning(f"Could not inject KB scope — falling back to default: {e}")

    async def _load_mcp_tools(
        self, mcp_servers: List["MCPServerConfig"]
    ) -> List[Any]:
        if not mcp_servers:
            return []

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            logger.warning(
                "langchain_mcp_adapters not installed — MCP tools unavailable. "
                "Run: uv add langchain-mcp-adapters"
            )
            return []

        server_map = {
            s.name: {"transport": "streamable_http", "url": s.url}
            for s in mcp_servers
        }

        client = MultiServerMCPClient(server_map)
        tools = await client.get_tools()
        logger.info(
            f"Loaded {len(tools)} MCP tools from: {list(server_map.keys())}"
        )
        return tools
