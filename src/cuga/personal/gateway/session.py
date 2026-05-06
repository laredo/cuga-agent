"""Session management: maps platform user identities to CUGA agent thread IDs."""

import uuid
from typing import Any, Dict, Optional

from cuga.personal.gateway.base import MessageEvent


class Session:
    """Holds state for one user on one platform."""

    def __init__(self, user_id: str, platform: str, thread_id: str):
        self.user_id = user_id
        self.platform = platform
        self.thread_id = thread_id
        self.user_context: Dict[str, Any] = {}
        self.active_skill: Optional[str] = None
        # Text of a bulletin (or other artifact) awaiting explicit user approval.
        # Set by the orchestrator or scheduler after a draft is delivered.
        self.pending_approval: Optional[str] = None
        self._agent = None  # lazily created CugaAgent

    def get_agent(self):
        """Return the CugaAgent for this session, creating it lazily."""
        if self._agent is None:
            from cuga import CugaAgent

            from cuga.personal.tools.knowledge import get_knowledge_tools

            self._agent = CugaAgent(tools=get_knowledge_tools())
        return self._agent


class SessionManager:
    """
    In-memory session store.  Maps (user_id, platform) → Session.

    Each session carries a stable thread_id used for CugaAgent.invoke()
    so conversation history is preserved across messages.
    """

    def __init__(self):
        # key: (user_id, platform)  value: Session
        self._sessions: Dict[tuple, Session] = {}

    async def get_or_create_session(self, event: MessageEvent) -> Session:
        key = (event.user_id, event.platform)

        if key not in self._sessions:
            thread_id = event.thread_id or str(uuid.uuid4())
            self._sessions[key] = Session(
                user_id=event.user_id,
                platform=event.platform,
                thread_id=thread_id,
            )
        elif event.thread_id and self._sessions[key].thread_id != event.thread_id:
            self._sessions[key].thread_id = event.thread_id

        return self._sessions[key]

    async def reset_session(self, user_id: str, platform: str) -> None:
        """Discard the current session so the next message starts fresh."""
        key = (user_id, platform)
        self._sessions.pop(key, None)

    def get_session(self, user_id: str, platform: str) -> Optional[Session]:
        """Synchronous lookup — returns None if no session exists."""
        return self._sessions.get((user_id, platform))
