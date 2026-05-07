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

        return CugaAgent(
            tools=tools or None,
            special_instructions=agent_cfg.instructions,
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
