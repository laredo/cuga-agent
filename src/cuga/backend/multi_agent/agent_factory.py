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
        # Single shared KnowledgeEngine for all agents in this topology.
        # All agents run in the same process; creating multiple KnowledgeEngine
        # instances against the same SQLite file causes locking errors.  One
        # engine + one KnowledgeClient per agent (different default_agent_id)
        # gives each agent its own namespace while sharing the underlying store.
        self._shared_kb_engine: Optional[Any] = None

    async def __aenter__(self) -> "AgentFactory":
        self._shared_kb_engine = self._create_kb_engine()
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

        # Inject a pre-built KnowledgeClient so all KB-enabled agents share
        # the same engine (and thus the same SQLite file) without conflicts.
        # Each agent gets its own default_agent_id for namespace isolation.
        if agent_cfg.enable_knowledge:
            self._inject_kb_scope(agent, agent_cfg.id)

        return agent

    def _create_kb_engine(self) -> Optional[Any]:
        """Create the single shared KnowledgeEngine for this topology."""
        try:
            from cuga.backend.knowledge.engine import KnowledgeEngine
            from cuga.backend.knowledge.config import KnowledgeConfig
            from cuga.config import settings

            config = KnowledgeConfig.from_settings(settings)
            engine = KnowledgeEngine(config)
            logger.info(
                f"Shared KB engine created for topology '{self._config.name}'"
            )
            return engine
        except Exception as e:
            logger.warning(f"Could not create shared KB engine: {e}")
            return None

    def _inject_kb_scope(self, agent: Any, agent_id: str) -> None:
        """Wire the shared KnowledgeEngine into this agent's KnowledgeClient.

        Uses the topology name as the default_agent_id so every agent in the
        topology writes to the same KB namespace and can read each other's
        documents.  The agent_id is logged for traceability but is not used
        as the KB scope — intentional: fact_checker:: / web_searcher:: prefixes
        in document titles carry provenance, not the KB namespace.
        """
        if self._shared_kb_engine is None:
            logger.warning(
                f"No shared KB engine — agent '{agent_id}' falls back to default KB"
            )
            return
        try:
            from cuga.backend.knowledge.client import KnowledgeClient

            agent._knowledge_client = KnowledgeClient(
                self._shared_kb_engine, default_agent_id=self._config.name
            )
            logger.info(
                f"KB scoped to topology '{self._config.name}' for agent '{agent_id}'"
            )
        except Exception as e:
            logger.warning(
                f"Could not inject KB scope for '{agent_id}' — falling back to default: {e}"
            )

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
