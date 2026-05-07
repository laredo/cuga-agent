"""Async message bus for routing AgentMessages between registered agents."""

import asyncio
from typing import Any, Callable, Dict, List, Optional

from cuga.backend.multi_agent.agent_message import AgentMessage


class _Registration:
    __slots__ = ("handler", "peers")

    def __init__(self, handler: Callable, peers: Optional[List[str]]):
        self.handler = handler
        # None means unrestricted (pipeline mode); [] means no peers allowed
        self.peers = peers


class AgentBus:
    def __init__(self, default_timeout: float = 30.0):
        self._agents: Dict[str, _Registration] = {}
        self._default_timeout = default_timeout

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        agent_id: str,
        handler: Callable,
        peers: Optional[List[str]] = None,
    ) -> None:
        if agent_id in self._agents:
            raise ValueError(f"{agent_id} is already registered")
        self._agents[agent_id] = _Registration(handler, peers)

    def deregister(self, agent_id: str) -> None:
        if agent_id not in self._agents:
            raise KeyError(f"{agent_id} is not registered")
        del self._agents[agent_id]

    def is_registered(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def registered_agents(self) -> List[str]:
        return list(self._agents.keys())

    # ------------------------------------------------------------------
    # Permission check (used by runner without sending)
    # ------------------------------------------------------------------

    def can_send(self, sender: str, recipient: str) -> bool:
        if recipient not in self._agents:
            return False
        reg = self._agents[recipient]
        if reg.peers is None:
            return True
        return sender in reg.peers

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send(self, message: AgentMessage) -> Any:
        if message.recipient not in self._agents:
            raise KeyError(f"{message.recipient} is not registered")

        reg = self._agents[message.recipient]

        if reg.peers is not None and message.sender not in reg.peers:
            raise PermissionError(
                f"{message.sender} is not a permitted peer of {message.recipient}"
            )

        return await asyncio.wait_for(
            reg.handler(message),
            timeout=self._default_timeout,
        )
