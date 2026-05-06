"""CLI channel adapter — stdin/stdout, reference implementation."""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional

from cuga.personal.gateway.base import ChannelAdapter, DeliveryTarget, MessageEvent, MessageType


class CLIAdapter(ChannelAdapter):
    """
    Simple stdin/stdout adapter for local development and testing.
    No auth required. One user per process.
    """

    platform = "cli"

    def __init__(self, user_id: str = "cli-user", channel_id: str = "cli-session"):
        self.user_id = user_id
        self.channel_id = channel_id
        self._running = False
        self._on_message: Optional[Callable] = None

    # ------------------------------------------------------------------
    # ChannelAdapter interface
    # ------------------------------------------------------------------

    async def start(self, on_message: Callable) -> None:
        """Start an interactive REPL loop reading from stdin."""
        self._on_message = on_message
        self._running = True
        print("CUGA Personal — type your message (Ctrl+C to quit)\n")
        while self._running:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, self._read_line)
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            event = self.collect_event(line)
            await on_message(event)

    async def stop(self) -> None:
        self._running = False

    async def send(self, target: DeliveryTarget, text: str, files: Optional[List[dict]] = None) -> None:
        print(f"\nAgent: {text}")
        if files:
            for f in files:
                print(f"  [file] {f.get('name', 'attachment')}")
        print()

    async def get_user_context(self, user_id: str) -> dict:
        return {"user_id": user_id, "platform": self.platform}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def collect_event(self, text: str) -> MessageEvent:
        """Build a MessageEvent from raw CLI input text."""
        msg_type = MessageType.COMMAND if text.strip().startswith("/") else MessageType.TEXT
        return MessageEvent(
            id=str(uuid.uuid4()),
            channel_id=self.channel_id,
            user_id=self.user_id,
            platform=self.platform,
            type=msg_type,
            text=text.strip(),
            timestamp=datetime.now(timezone.utc),
        )

    def _read_line(self) -> str:
        try:
            return input("You: ")
        except EOFError:
            return ""
